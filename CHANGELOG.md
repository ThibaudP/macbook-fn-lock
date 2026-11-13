# Changelog

## 0.1.0 — 2026-11-13

First release.

- Double-tap Fn to switch between multimedia keys and F1–F12.
- Compact GNOME panel icon, neutral for multimedia mode and blue for F1–F12.
- Menu with a fixed Fn Lock switch, a separate current-mode label, and a short gesture hint.
- Keep the menu open while switching modes.
- Persist the selected mode across reboots.
- Cancel mixed-key gestures, long holds, and autorepeat; handle keyboard reconnection and dropped events.
- Restrict D-Bus mode changes to an active local session through polkit.
- Include installation, removal, live-reload, and release-packaging tools.

Targets GNOME Shell 51 and Apple keyboards using `hid_apple` with `KEY_FN`. Checked on MacBookPro10,2, Ubuntu 26.10, GNOME Shell 51, and Wayland.
