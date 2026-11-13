#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
python_bin=${PYTHON:-/usr/bin/python3}
"$python_bin" -m unittest discover -s tests -v
"$python_bin" tests/check_extension.py
for script in install.sh uninstall.sh scripts/*.sh; do
    sh -n "$script"
done
