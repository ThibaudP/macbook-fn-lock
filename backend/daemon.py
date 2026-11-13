#!/usr/bin/python3
"""Observe Apple Fn events without grabbing or injecting keyboard input."""

import fcntl
import logging
import os
from pathlib import Path
import signal
import struct
import sys
import time

from gi.repository import Gio, GLib

from core import DoubleTap, KEY_COUNT, KEY_FN, ModeStore, bitmap_has_key

NAME = "org.gnome.Shell.Extensions.AppleFnLock"
OBJECT_PATH = "/org/gnome/Shell/Extensions/AppleFnLock"
ACTION = "org.gnome.shell.extensions.apple-fn-lock.set-mode"
MODE_PATH = Path("/sys/module/hid_apple/parameters/fnmode")
STATE_DIR = Path("/var/lib/apple-fn-lock")
INPUT_SYSFS = Path("/sys/class/input")
INPUT_DEVICES = Path("/dev/input")
EVENT = struct.Struct("@llHHi")
EV_KEY, EV_SYN = 1, 0
SYN_REPORT, SYN_DROPPED = 0, 3
KEY_BYTES = KEY_COUNT // 8
EVIOCGKEY = 0x80004518 | (KEY_BYTES << 16)
EVIOCSCLOCKID = 0x400445A0
LOG = logging.getLogger("apple-fn-lock")


class Keyboard:
    def __init__(self, path, on_toggle):
        self.path = path
        self.on_toggle = on_toggle
        self.detector = DoubleTap()
        self.dropped = False
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.source = 0
        try:
            # Event timestamps must remain comparable across queue delays.
            fcntl.ioctl(self.fd, EVIOCSCLOCKID, struct.pack("@i", time.CLOCK_MONOTONIC))
            self.resync()
            self.source = GLib.io_add_watch(
                self.fd, GLib.PRIORITY_DEFAULT,
                GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR | GLib.IO_NVAL,
                self.read_events,
            )
        except Exception:
            os.close(self.fd)
            self.fd = -1
            raise

    def resync(self):
        keys = bytearray(KEY_BYTES)
        fcntl.ioctl(self.fd, EVIOCGKEY, keys, True)
        self.detector.resync(
            code for code in range(KEY_COUNT) if keys[code // 8] & (1 << (code % 8))
        )

    def read_events(self, _fd, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR | GLib.IO_NVAL):
            self.close(from_callback=True)
            return GLib.SOURCE_REMOVE
        try:
            # Bound each dispatch so input cannot starve D-Bus and hotplug checks.
            for _ in range(8):
                try:
                    data = os.read(self.fd, EVENT.size * 64)
                except BlockingIOError:
                    break
                if not data:
                    self.close(from_callback=True)
                    return GLib.SOURCE_REMOVE
                for seconds, micros, kind, code, value in EVENT.iter_unpack(data):
                    if kind == EV_SYN and code == SYN_DROPPED:
                        self.dropped = True
                        self.detector.reset()
                    elif self.dropped:
                        if kind == EV_SYN and code == SYN_REPORT:
                            self.resync()
                            self.dropped = False
                    elif kind == EV_KEY:
                        if self.detector.feed(code, value, seconds + micros / 1_000_000):
                            self.on_toggle()
        except (OSError, ValueError, struct.error):
            LOG.exception("Keyboard disconnected or input stream could not be read")
            self.close(from_callback=True)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def close(self, from_callback=False):
        if self.source and not from_callback:
            GLib.source_remove(self.source)
        self.source = 0
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        self.detector.resync()


class Service:
    def __init__(self, connection, store):
        self.connection = connection
        self.store = store
        self.keyboards = {}
        self.properties = {}
        self.previously_available = False
        interface = Path(__file__).with_name("interface.xml").read_text()
        info = Gio.DBusNodeInfo.new_for_xml(interface).interfaces[0]
        self.registration = connection.register_object(
            OBJECT_PATH, info, self.method_call, self.get_property, None,
        )
        self.scan()
        self.timer = GLib.timeout_add_seconds(2, self.scan)

    def get_property(self, _connection, _sender, _path, _interface, name):
        return self.properties[name]

    def refresh(self):
        try:
            mode = self.store.read()
            available = True
        except (OSError, ValueError):
            mode, available = -1, False
        values = {
            "Locked": GLib.Variant("b", mode == 2),
            "Mode": GLib.Variant("i", mode),
            "Available": GLib.Variant("b", available),
            "KeyboardConnected": GLib.Variant("b", bool(self.keyboards)),
        }
        changes = {key: value for key, value in values.items()
                   if self.properties.get(key) != value}
        self.properties = values
        if changes:
            self.connection.emit_signal(
                None, OBJECT_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (NAME, changes, [])),
            )
        return available

    def scan(self):
        candidates = set()
        for entry in INPUT_SYSFS.glob("event*"):
            try:
                device = entry / "device"
                if int((device / "id/vendor").read_text().strip(), 16) != 0x05AC:
                    continue
                if not bitmap_has_key((device / "capabilities/key").read_text(), KEY_FN):
                    continue
                # Only keyboards bound to hid_apple can be controlled by fnmode.
                if not any((parent / "driver").resolve().name == "apple"
                           for parent in device.resolve().parents):
                    continue
            except (OSError, ValueError):
                continue
            path = INPUT_DEVICES / entry.name
            candidates.add(path)
            existing = self.keyboards.get(path)
            if existing is not None and existing.fd >= 0:
                continue
            try:
                self.keyboards[path] = Keyboard(path, self.toggle)
                LOG.info("Watching Apple Fn key on %s", path)
            except OSError as error:
                if existing is not None:
                    self.keyboards.pop(path, None)
                LOG.debug("Cannot open %s: %s", path, error)
        for path in set(self.keyboards) - candidates:
            self.keyboards.pop(path).close()
        # A disconnected fd may remain until the next scan.
        for path in list(self.keyboards):
            if self.keyboards[path].fd < 0:
                self.keyboards.pop(path).close()
        available = self.refresh()
        if available and not self.previously_available:
            try:
                self.store.restore()
            except (OSError, ValueError):
                LOG.exception("Could not restore saved Fn mode")
            self.refresh()
        self.previously_available = available
        return GLib.SOURCE_CONTINUE

    def set_locked(self, locked):
        self.store.set_locked(locked)
        self.refresh()

    def toggle(self):
        try:
            self.set_locked(self.store.read() != 2)
        except (OSError, ValueError):
            LOG.exception("Could not toggle Fn Lock")
            self.refresh()

    def method_call(self, connection, sender, _path, _interface, method, parameters, invocation):
        if method != "SetLocked":
            invocation.return_dbus_error(NAME + ".UnknownMethod", "Unknown method")
            return
        # Ask polkit about the actual bus sender. No prompt or cached authority.
        subject = ("system-bus-name", {"name": GLib.Variant("s", sender)})
        request = GLib.Variant("((sa{sv})sa{ss}us)", (subject, ACTION, {}, 0, ""))
        connection.call(
            "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization", request,
            GLib.VariantType.new("((bba{ss}))"), Gio.DBusCallFlags.NONE, 5000,
            None, self.authorized, (invocation, parameters.unpack()[0]),
        )

    def authorized(self, connection, result, data):
        invocation, locked = data
        try:
            allowed = connection.call_finish(result).unpack()[0][0]
        except GLib.Error:
            allowed = False
        if not allowed:
            invocation.return_dbus_error(NAME + ".NotAuthorized", "An active local session is required")
            return
        try:
            self.set_locked(locked)
        except (OSError, ValueError) as error:
            self.refresh()
            invocation.return_dbus_error(NAME + ".Failed", str(error))
        else:
            invocation.return_value(GLib.Variant("()", ()))

    def close(self):
        GLib.source_remove(self.timer)
        for keyboard in self.keyboards.values():
            keyboard.close()
        self.connection.unregister_object(self.registration)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    loop = GLib.MainLoop()
    services = []
    failed = False

    def bus_acquired(connection, _name):
        nonlocal failed
        try:
            services.append(Service(connection, ModeStore(MODE_PATH, STATE_DIR)))
        except Exception:
            LOG.exception("Could not initialize Apple Fn Lock")
            failed = True
            loop.quit()

    def quit_loop(*_args):
        loop.quit()
        return GLib.SOURCE_REMOVE

    def name_lost(*_args):
        nonlocal failed
        LOG.error("Lost the Apple Fn Lock system bus name")
        failed = True
        loop.quit()

    owner = Gio.bus_own_name(
        Gio.BusType.SYSTEM, NAME, Gio.BusNameOwnerFlags.NONE,
        bus_acquired, None, name_lost,
    )
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, quit_loop)
    try:
        loop.run()
    finally:
        for service in services:
            service.close()
        Gio.bus_unown_name(owner)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
