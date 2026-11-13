#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
extension_id=apple-fn-lock@thibaudp.github.io
extension_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$extension_id"

if [ "$(id -u)" -eq 0 ]; then
    echo 'Run ./install.sh as your desktop user, without sudo.' >&2
    exit 1
fi
if ! command -v gnome-extensions >/dev/null 2>&1; then
    echo 'GNOME Shell and gnome-extensions are required.' >&2
    exit 1
fi
shell_major=$(gnome-shell --version | awk '{split($3, version, "."); print version[1]}')
if [ "$shell_major" != 51 ]; then
    echo "This release targets GNOME Shell 51; detected: $shell_major." >&2
    exit 1
fi

sudo "$project_dir/scripts/install-system.sh"
install -d -m 755 "$extension_dir"
install -m 644 "$project_dir/extension/extension.js" "$extension_dir/extension.js"
install -m 644 "$project_dir/extension/metadata.json" "$extension_dir/metadata.json"
install -m 644 "$project_dir/data/interface.xml" "$extension_dir/interface.xml"

if gnome-extensions enable "$extension_id"; then
    echo 'MacBook Fn Lock installed. Look for Fn in the top bar and double-tap Fn.'
else
    echo 'Installed. Log out and back in, then run:'
    echo "  gnome-extensions enable $extension_id"
fi
