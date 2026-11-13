import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from gi.repository import Gio, GLib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import daemon
from core import KEY_FN, ModeStore


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.fd, self.writer = os.pipe2(os.O_NONBLOCK)
        self.addCleanup(os.close, self.writer)
        self.toggle = Mock()
        with patch.object(daemon.os, "open", return_value=self.fd), \
                patch.object(daemon.fcntl, "ioctl"), \
                patch.object(GLib, "io_add_watch", return_value=0):
            self.keyboard = daemon.Keyboard(Path("/unused"), self.toggle)
        self.addCleanup(self.keyboard.close)

    def event(self, timestamp, kind, code, value):
        seconds = int(timestamp)
        return daemon.EVENT.pack(seconds, round((timestamp - seconds) * 1_000_000), kind, code, value)

    def tap(self, timestamp):
        return (self.event(timestamp, 1, KEY_FN, 1) +
                self.event(timestamp + 0.05, 1, KEY_FN, 0))

    def test_complete_binary_stream_toggles_once_without_grabbing(self):
        os.write(self.writer, self.tap(1) + self.tap(1.2))
        self.assertTrue(self.keyboard.read_events(self.fd, GLib.IO_IN))
        self.toggle.assert_called_once_with()

    def test_dropped_events_reset_gesture_until_syn_report(self):
        data = self.tap(1) + self.event(1.1, 0, 3, 0) + self.tap(1.2) + self.event(1.3, 0, 0, 0)
        os.write(self.writer, data)
        with patch.object(daemon.fcntl, "ioctl"):
            self.keyboard.read_events(self.fd, GLib.IO_IN)
        self.toggle.assert_not_called()
        os.write(self.writer, self.tap(1.35) + self.tap(1.5))
        self.keyboard.read_events(self.fd, GLib.IO_IN)
        self.toggle.assert_called_once_with()

    def test_hangup_closes_descriptor_and_resets_gesture(self):
        self.assertFalse(self.keyboard.read_events(self.fd, GLib.IO_HUP))
        self.assertEqual(self.keyboard.fd, -1)
        self.assertIsNone(self.keyboard.detector.first_tap)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "fnmode"
        path.write_text("3\n")
        self.connection = Mock()
        self.service = daemon.Service.__new__(daemon.Service)
        self.service.connection = self.connection
        self.service.store = ModeStore(path, Path(self.temp.name) / "state")
        self.service.store.restore()
        self.service.properties = {}
        self.service.keyboards = {}
        self.service.refresh()
        self.connection.reset_mock()

    def invocation(self, method="SetLocked"):
        invocation = Mock()
        self.service.method_call(self.connection, ":1.42", daemon.OBJECT_PATH,
                                 daemon.NAME, method, GLib.Variant("(b)", (True,)), invocation)
        return invocation

    def authorize(self, invocation, allowed):
        self.connection.call_finish.return_value = GLib.Variant("((bba{ss}))", ((allowed, False, {}),))
        self.service.authorized(self.connection, object(), (invocation, True))

    def test_authorizes_actual_sender_without_interaction(self):
        invocation = self.invocation()
        args = self.connection.call.call_args.args
        subject, action, details, flags, cancellation = args[4].unpack()
        self.assertEqual(subject, ("system-bus-name", {"name": ":1.42"}))
        self.assertEqual(action, daemon.ACTION)
        self.assertEqual((details, flags, cancellation), ({}, 0, ""))
        self.assertEqual(self.service.store.read(), 3)
        self.authorize(invocation, True)
        self.assertEqual(self.service.store.read(), 2)
        invocation.return_value.assert_called_once()

    def test_denied_sender_cannot_change_mode(self):
        invocation = self.invocation()
        self.authorize(invocation, False)
        self.assertEqual(self.service.store.read(), 3)
        self.assertEqual(invocation.return_dbus_error.call_args.args[0], daemon.NAME + ".NotAuthorized")

    def test_polkit_failure_denies_request(self):
        invocation = self.invocation()
        self.connection.call_finish.side_effect = GLib.Error("polkit unavailable")
        self.service.authorized(self.connection, object(), (invocation, True))
        self.assertEqual(self.service.store.read(), 3)
        invocation.return_dbus_error.assert_called_once()

    def test_unknown_method_never_calls_polkit(self):
        invocation = self.invocation("WriteArbitraryFile")
        self.connection.call.assert_not_called()
        invocation.return_dbus_error.assert_called_once()

    def test_changed_properties_include_locked_state(self):
        self.service.set_locked(True)
        signal = self.connection.emit_signal.call_args.args
        self.assertEqual(signal[3], "PropertiesChanged")
        interface, changed, invalidated = signal[4].unpack()
        self.assertEqual(interface, daemon.NAME)
        self.assertEqual(changed, {"Locked": True, "Mode": 2})
        self.assertEqual(invalidated, [])
        self.connection.reset_mock()
        self.service.refresh()
        self.connection.emit_signal.assert_not_called()

    def test_missing_kernel_module_is_reported_unavailable(self):
        self.service.store.mode_path.unlink()
        self.service.refresh()
        self.assertFalse(self.service.properties["Available"].unpack())
        self.assertEqual(self.service.properties["Mode"].unpack(), -1)

    def test_public_interface_has_no_arbitrary_write_operation(self):
        info = Gio.DBusNodeInfo.new_for_xml((ROOT / "data/interface.xml").read_text()).interfaces[0]
        self.assertEqual([method.name for method in info.methods], ["SetLocked"])
        self.assertEqual(info.methods[0].in_args[0].signature, "b")

    def keyboard_fixture(self):
        root = Path(self.temp.name)
        sysfs = root / "sys/class/input"
        device = root / "devices/hid/input/input6"
        (device / "id").mkdir(parents=True)
        (device / "capabilities").mkdir()
        (device / "id/vendor").write_text("05ac\n")
        words = [0] * (KEY_FN // 64 + 1)
        words[KEY_FN // 64] = 1 << (KEY_FN % 64)
        (device / "capabilities/key").write_text(" ".join(f"{word:x}" for word in reversed(words)))
        driver = root / "drivers/apple"
        driver.mkdir(parents=True)
        (root / "devices/hid/driver").symlink_to(driver, target_is_directory=True)
        entry = sysfs / "event6"
        entry.mkdir(parents=True)
        (entry / "device").symlink_to(device, target_is_directory=True)
        self.service.previously_available = False
        return sysfs, entry

    def test_hotplug_disconnect_and_reconnect(self):
        sysfs, entry = self.keyboard_fixture()
        first, second = Mock(fd=10), Mock(fd=11)
        with patch.object(daemon, "INPUT_SYSFS", sysfs), \
                patch.object(daemon, "Keyboard", side_effect=[first, second]) as keyboard_class:
            self.service.scan()
            self.assertTrue(self.service.properties["KeyboardConnected"].unpack())
            self.service.scan()
            self.assertEqual(keyboard_class.call_count, 1)
            device = (entry / "device").resolve()
            (entry / "device").unlink()
            self.service.scan()
            first.close.assert_called_once()
            self.assertFalse(self.service.properties["KeyboardConnected"].unpack())
            (entry / "device").symlink_to(device, target_is_directory=True)
            self.service.scan()
            self.assertEqual(keyboard_class.call_count, 2)
            self.assertTrue(self.service.properties["KeyboardConnected"].unpack())

    def test_non_apple_and_wrong_driver_are_not_opened(self):
        sysfs, entry = self.keyboard_fixture()
        device = (entry / "device").resolve()
        with patch.object(daemon, "INPUT_SYSFS", sysfs), \
                patch.object(daemon, "Keyboard") as keyboard_class:
            (device / "id/vendor").write_text("1234")
            self.service.scan()
            keyboard_class.assert_not_called()
            (device / "id/vendor").write_text("05ac")
            (device.parents[1] / "driver").unlink()
            self.service.scan()
            keyboard_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
