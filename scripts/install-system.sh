#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$(id -u)" -ne 0 ]; then
    echo 'The system service installer requires sudo.' >&2
    exit 1
fi
if ! /usr/bin/python3 -s -c 'from gi.repository import Gio, GLib' >/dev/null 2>&1; then
    echo 'Install dependencies first: sudo apt install python3-gi' >&2
    exit 1
fi
if [ ! -e /sys/module/hid_apple/parameters/fnmode ]; then
    echo 'hid_apple fnmode was not found; an Apple keyboard using hid_apple is required.' >&2
    exit 1
fi
if ! command -v busctl >/dev/null 2>&1 || ! command -v pkaction >/dev/null 2>&1; then
    echo 'Install systemd and polkit before installing MacBook Fn Lock.' >&2
    exit 1
fi

install -d -m 755 /usr/local/lib/apple-fn-lock /etc/dbus-1/system.d /etc/systemd/system
install -d -m 755 /usr/share/polkit-1/actions
install -m 644 "$project_dir/backend/core.py" /usr/local/lib/apple-fn-lock/core.py
install -m 644 "$project_dir/backend/daemon.py" /usr/local/lib/apple-fn-lock/daemon.py
install -m 644 "$project_dir/data/interface.xml" /usr/local/lib/apple-fn-lock/interface.xml
install -m 644 "$project_dir/data/apple-fn-lock.service" /etc/systemd/system/apple-fn-lock.service
install -m 644 "$project_dir/data/org.gnome.Shell.Extensions.AppleFnLock.conf" /etc/dbus-1/system.d/org.gnome.Shell.Extensions.AppleFnLock.conf
install -m 644 "$project_dir/data/org.gnome.shell.extensions.apple-fn-lock.policy" /usr/share/polkit-1/actions/org.gnome.shell.extensions.apple-fn-lock.policy

busctl --system call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig
systemctl daemon-reload
systemctl enable apple-fn-lock.service
systemctl restart apple-fn-lock.service
echo 'Apple Fn Lock system service installed.'
