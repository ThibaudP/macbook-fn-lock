#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
extension_id=apple-fn-lock@thibaudp.github.io
extension_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$extension_id"
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run ./uninstall.sh as your desktop user, without sudo.' >&2
    exit 1
fi

sudo "$project_dir/scripts/uninstall-system.sh"
gnome-extensions disable "$extension_id" 2>/dev/null || true
for file in extension.js metadata.json interface.xml; do
    rm -f -- "$extension_dir/$file"
done
if [ -d "$extension_dir" ]; then rmdir -- "$extension_dir"; fi
echo 'MacBook Fn Lock uninstalled. The original Fn mode has been restored.'
