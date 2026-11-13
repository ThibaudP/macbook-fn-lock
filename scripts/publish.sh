#!/bin/sh
# Publish the already prepared Git repository to the authenticated GitHub account.
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
if ! command -v gh >/dev/null 2>&1; then
    echo 'Install GitHub CLI and run gh auth login first.' >&2
    exit 1
fi
gh auth status
if [ "$(git rev-parse --show-toplevel)" != "$project_dir" ]; then
    echo 'Initialize and commit this project as its own Git repository first.' >&2
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo 'Commit project changes before publishing.' >&2
    exit 1
fi
if git remote get-url origin >/dev/null 2>&1; then
    echo 'An origin remote already exists. Review it and use git push to update it.' >&2
    exit 1
fi
gh repo create macbook-fn-lock --public --source . --remote origin --push \
    --description 'Double-tap Fn to toggle Fn Lock on Apple keyboards, with a GNOME top-bar indicator. MIT licensed.'
