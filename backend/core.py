"""Keyboard gesture and hid_apple mode handling; no desktop dependencies."""

import logging
from pathlib import Path
import struct

KEY_FN = 464
KEY_COUNT = 768
LOG = logging.getLogger("apple-fn-lock")


def bitmap_has_key(bitmap, key):
    """Decode Linux sysfs bitmaps (most significant native word first)."""
    word_bits = struct.calcsize("@L") * 8
    words = bitmap.split()
    word = key // word_bits
    return word < len(words) and bool(int(words[-1 - word], 16) & (1 << (key % word_bits)))


class DoubleTap:
    """Two complete, short Fn taps within 500 ms, without intervening keys."""

    def __init__(self, window=0.5, max_hold=0.25):
        self.window = window
        self.max_hold = max_hold
        self.held = set()
        self.reset()

    def reset(self):
        self.started = None
        self.first_tap = None

    def resync(self, held=()):
        self.reset()
        self.held = set(held)

    def feed(self, code, value, timestamp):
        if code != KEY_FN:
            self.reset()
            if value == 1:
                self.held.add(code)
            elif value == 0:
                self.held.discard(code)
            return False
        if value == 2:  # Autorepeat is never another tap.
            return False
        if value == 1:
            if KEY_FN in self.held:
                self.reset()
                return False
            self.held.add(KEY_FN)
            if self.held != {KEY_FN}:
                self.reset()
            else:
                self.started = timestamp
            return False
        if value != 0:
            return False
        self.held.discard(KEY_FN)
        started, self.started = self.started, None
        if (started is None or self.held or
                not 0 <= timestamp - started <= self.max_hold):
            self.reset()
            return False
        first = self.first_tap
        if first is not None and 0 <= timestamp - first <= self.window:
            self.reset()
            return True
        self.first_tap = started
        return False


class ModeStore:
    """Write only fnmode, preserving the pre-install mode for uninstall."""

    def __init__(self, mode_path, state_dir):
        self.mode_path = Path(mode_path)
        self.state_dir = Path(state_dir)

    def read(self):
        value = int(self.mode_path.read_text().strip())
        if value not in range(5):
            raise ValueError(f"Unexpected hid_apple fnmode: {value}")
        return value

    def restore(self):
        current = self.read()
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        original = self.state_dir / "original-mode"
        if not original.exists():
            original.write_text(f"{current}\n")
        saved = self.state_dir / "mode"
        if saved.exists():
            try:
                mode = int(saved.read_text().strip())
            except ValueError:
                LOG.warning("Ignoring invalid saved mode")
                return
            if mode in (1, 2):
                self.mode_path.write_text(f"{mode}\n")

    def set_locked(self, locked):
        mode = 2 if locked else 1
        self.mode_path.write_text(f"{mode}\n")
        try:
            self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary = self.state_dir / "mode.tmp"
            temporary.write_text(f"{mode}\n")
            temporary.replace(self.state_dir / "mode")
        except OSError:
            # The requested hardware mode is active even if persistence failed.
            LOG.exception("Mode changed, but could not save it for the next boot")
