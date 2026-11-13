# MacBook Fn Lock

Double-tap **Fn** to switch an Apple keyboard between media keys and **F1–F12**, with a GNOME top-bar indicator and menu switch.

| Fn key icon | Press a top-row key | Hold Fn + top-row key |
| --- | --- | --- |
| Neutral | Volume, brightness, playback… | F1–F12 |
| Blue | F1–F12 | Volume, brightness, playback… |

The two short taps must finish within 500 ms. Holding Fn, using Fn with another key, or typing between taps cancels the gesture. Ordinary keyboard events continue to GNOME unchanged. The chosen mode is remembered across reboots.

## Requirements

- Linux with an Apple keyboard using the kernel's `hid_apple` driver and exposing `KEY_FN`.
- GNOME Shell **51**, including Wayland sessions.
- Python 3 with PyGObject (`python3-gi` on Ubuntu), systemd, D-Bus and polkit.
- Administrator access for the small system service.

Developed against a MacBookPro10,2 running Ubuntu 26.10 and GNOME Shell 51. Automated tests cover the gesture, state storage, input stream handling, D-Bus authorization and extension lifecycle. **Physical double-tap behavior and the live GNOME UI still require on-device validation.** Other Shell versions are not yet advertised as supported.

## Install

Clone or download this repository, then run as your normal desktop user:

```sh
./install.sh
```

The installer requests sudo once for the service. It installs the GNOME extension for your user and tries to enable it. If GNOME has not discovered the new extension, log out and back in, then run:

```sh
gnome-extensions enable apple-fn-lock@thibaudp.github.io
```

Look for the small `fn` key icon in the top bar. Blue means Fn Lock is active. Open its menu to select F1–F12 directly, or double-tap Fn.

To load or update the extension in the current session, press **Alt+F2**, enter `lg`, and run the following in the Evaluator, replacing `/path/to/macbook-fn-lock` with this checkout's absolute path:

```js
await (await import('file:///path/to/macbook-fn-lock/scripts/reload-in-shell.js')).reload()
```

Press Escape to close Looking Glass. This development helper loads the installed files without enabling D-Bus evaluation or restarting the session.

## Uninstall

```sh
./uninstall.sh
```

This removes the service, extension, D-Bus and polkit configuration, and saved state. It restores the kernel Fn mode recorded before the service's first run. No modprobe configuration or initramfs changes are made.

## How it works

A system service observes Apple keyboard events through evdev and switches `/sys/module/hid_apple/parameters/fnmode` between `1` (media first) and `2` (F1–F12 first). It never grabs the keyboard or injects replacement key events. Fn+arrows and Fn+Backspace keep their normal kernel behavior.

The service reads key codes only to recognize Fn and cancel mixed-key gestures. It does not record, log or export typed text or individual key events. Users do not receive general access to input devices or permission to write kernel settings. Only the narrow `SetLocked(bool)` operation is exposed over the system bus; polkit permits it for an active local session. The GNOME extension displays the current mode and calls that operation.

Disconnects and dropped evdev events reset gesture detection. Newly connected Apple keyboards are discovered within about two seconds. The kernel setting applies to **all keyboards handled by `hid_apple`**, rather than one individual device. The service continues recognizing the gesture when the extension is disabled; stop the service to disable it entirely.

## Troubleshooting

```sh
systemctl status apple-fn-lock.service
journalctl -u apple-fn-lock.service -b
cat /sys/module/hid_apple/parameters/fnmode
gnome-extensions info apple-fn-lock@thibaudp.github.io
```

An amber icon means the service or kernel driver is unavailable; the menu gives the reason. If the menu says the keyboard was not detected, verify that it exposes `KEY_FN` and uses `hid_apple`; the menu switch can still change the driver's mode. A keyboard whose firmware hides Fn cannot provide the double-tap gesture through this implementation.

`swap_fn_leftctrl=1` changes which physical key emits `KEY_FN`; the gesture follows that emitted key. If you expect the physical Fn key, keep `swap_fn_leftctrl=0`.

## Development

```sh
make check
make package
```

`make check` requires Python with PyGObject and GJS. Tests use temporary state files, synthetic input events and a simulated D-Bus connection. They do not access your keyboard or change its mode. The GJS harness validates the extension's lifecycle using simulated Shell widgets; it does not replace a test inside GNOME Shell. `make package` produces a source archive and an extension ZIP in `dist/`; the ZIP alone does not install the required service.

Without Make, run `./scripts/check.sh` and `python3 scripts/package.py` directly.

For the maintainer's initial public GitHub publication, commit the project and run `./scripts/publish.sh` after authenticating GitHub CLI with `gh auth login`. This creates a public `macbook-fn-lock` repository in the authenticated account and pushes the local commits. Subsequent updates use `git push`.

Sources: [Linux hid-apple driver](https://code.googlesource.com/linux/torvalds/linux/+/7acf90feab8b009fde7def08ff2c622d0f10e99f/drivers/hid/hid-apple.c), [GNOME extension documentation](https://gjs.guide/extensions/), [polkit documentation](https://www.freedesktop.org/software/polkit/docs/latest/polkit.8.html).

## License

[MIT](LICENSE), © 2026 Thibaud Poncin.
