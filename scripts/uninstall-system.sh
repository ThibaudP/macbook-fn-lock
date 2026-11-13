#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo 'The system service uninstaller requires sudo.' >&2
    exit 1
fi
systemctl disable --now apple-fn-lock.service
/usr/bin/python3 -I - <<'PY'
from pathlib import Path

original = Path('/var/lib/apple-fn-lock/original-mode')
target = Path('/sys/module/hid_apple/parameters/fnmode')
if original.exists() and target.exists():
    mode = int(original.read_text().strip())
    if mode not in range(5):
        raise SystemExit('Invalid original mode: refusing to overwrite fnmode')
    target.write_text(f'{mode}\n')
PY
rm -f /etc/systemd/system/apple-fn-lock.service
rm -f /etc/dbus-1/system.d/org.gnome.Shell.Extensions.AppleFnLock.conf
rm -f /usr/share/polkit-1/actions/org.gnome.shell.extensions.apple-fn-lock.policy
rm -f /usr/local/lib/apple-fn-lock/core.py /usr/local/lib/apple-fn-lock/daemon.py /usr/local/lib/apple-fn-lock/interface.xml
rm -f /var/lib/apple-fn-lock/mode /var/lib/apple-fn-lock/mode.tmp /var/lib/apple-fn-lock/original-mode
for directory in /usr/local/lib/apple-fn-lock /var/lib/apple-fn-lock; do
    if [ -d "$directory" ]; then rmdir "$directory"; fi
done
systemctl daemon-reload
busctl --system call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig
