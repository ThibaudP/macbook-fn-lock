import sys
import tempfile
from pathlib import Path
import struct
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from core import DoubleTap, KEY_FN, ModeStore, bitmap_has_key


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.gesture = DoubleTap()

    def tap(self, start, duration=0.06):
        self.assertFalse(self.gesture.feed(KEY_FN, 1, start))
        return self.gesture.feed(KEY_FN, 0, start + duration)

    def test_two_taps_toggle_on_second_release(self):
        self.assertFalse(self.tap(0))
        self.assertTrue(self.tap(0.18))

    def test_single_tap_does_not_toggle(self):
        self.assertFalse(self.tap(0))

    def test_slow_taps_start_new_pair(self):
        self.assertFalse(self.tap(0))
        self.assertFalse(self.tap(1))
        self.assertTrue(self.tap(1.2))

    def test_long_hold_is_not_a_tap(self):
        self.assertFalse(self.tap(0, 1))
        self.assertFalse(self.tap(1.1))

    def test_fn_chord_cancels_pair(self):
        self.tap(0)
        self.gesture.feed(KEY_FN, 1, 0.15)
        self.gesture.feed(115, 1, 0.18)
        self.gesture.feed(115, 0, 0.19)
        self.assertFalse(self.gesture.feed(KEY_FN, 0, 0.22))
        self.assertFalse(self.tap(0.3))

    def test_typing_between_taps_cancels_pair(self):
        self.tap(0)
        self.gesture.feed(30, 1, 0.1)
        self.gesture.feed(30, 0, 0.11)
        self.assertFalse(self.tap(0.2))

    def test_modifier_already_held_cancels(self):
        self.gesture.feed(29, 1, 0)
        self.assertFalse(self.tap(0.1))
        self.assertFalse(self.tap(0.25))
        self.gesture.feed(29, 0, 0.35)
        self.assertFalse(self.tap(0.4))
        self.assertTrue(self.tap(0.6))

    def test_autorepeat_does_not_toggle(self):
        self.gesture.feed(KEY_FN, 1, 0)
        for timestamp in (0.01, 0.02, 0.03):
            self.assertFalse(self.gesture.feed(KEY_FN, 2, timestamp))
        self.assertFalse(self.gesture.feed(KEY_FN, 0, 0.04))

    def test_four_taps_toggle_twice(self):
        self.assertEqual([self.tap(t) for t in (0, 0.15, 0.3, 0.45)], [False, True, False, True])

    def test_resync_discards_old_pair_and_accounts_for_held_keys(self):
        self.tap(0)
        self.gesture.resync([29])
        self.assertFalse(self.tap(0.2))
        self.gesture.feed(29, 0, 0.3)
        self.assertFalse(self.tap(0.4))

    def test_release_without_press_is_ignored(self):
        self.assertFalse(self.gesture.feed(KEY_FN, 0, 0))
        self.assertFalse(self.tap(0.1))

    def test_clock_reversal_does_not_toggle(self):
        self.tap(10)
        self.assertFalse(self.tap(1))


class BitmapTests(unittest.TestCase):
    def test_native_words_preserve_leading_zeroes(self):
        word_bits = struct.calcsize("@L") * 8
        words = [0] * (KEY_FN // word_bits + 1)
        words[KEY_FN // word_bits] |= 1 << (KEY_FN % word_bits)
        bitmap = " ".join(f"{word:x}" for word in reversed(words))
        self.assertTrue(bitmap_has_key(bitmap, KEY_FN))
        self.assertFalse(bitmap_has_key(bitmap, KEY_FN - 1))
        self.assertFalse(bitmap_has_key(bitmap, KEY_FN + word_bits))

    def test_keyboard_without_fn(self):
        self.assertFalse(bitmap_has_key("ff 0 fffffffffffffffe", KEY_FN))


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mode = self.root / "fnmode"
        self.mode.write_text("3\n")
        self.store = ModeStore(self.mode, self.root / "state")

    def test_first_start_preserves_auto_mode(self):
        self.store.restore()
        self.assertEqual(self.store.read(), 3)
        self.assertEqual((self.store.state_dir / "original-mode").read_text(), "3\n")

    def test_toggle_writes_kernel_mode_and_persists(self):
        self.store.restore()
        self.store.set_locked(True)
        self.assertEqual(self.store.read(), 2)
        self.assertEqual((self.store.state_dir / "mode").read_text(), "2\n")
        self.store.set_locked(False)
        self.assertEqual(self.store.read(), 1)

    def test_restart_restores_selection_and_preserves_original(self):
        self.store.restore()
        self.store.set_locked(True)
        self.mode.write_text("3\n")
        self.store.restore()
        self.assertEqual(self.store.read(), 2)
        self.assertEqual((self.store.state_dir / "original-mode").read_text(), "3\n")

    def test_invalid_saved_mode_is_ignored(self):
        self.store.restore()
        (self.store.state_dir / "mode").write_text("garbage")
        self.store.restore()
        self.assertEqual(self.store.read(), 3)

    def test_kernel_write_failure_does_not_save_selection(self):
        self.store.restore()
        self.mode.unlink()
        self.mode.mkdir()
        with self.assertRaises(OSError):
            self.store.set_locked(True)
        self.assertFalse((self.store.state_dir / "mode").exists())

    def test_unexpected_kernel_value_is_rejected(self):
        self.mode.write_text("99")
        with self.assertRaises(ValueError):
            self.store.read()


if __name__ == "__main__":
    unittest.main()
