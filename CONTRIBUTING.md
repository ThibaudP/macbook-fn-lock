# Contributing

Bug reports, compatibility results, and focused pull requests are welcome.

## Report a problem

Include your MacBook or keyboard model, distribution, GNOME Shell version, and whether you use Wayland or X11. Describe the expected behavior and what happened. These commands help identify the setup:

```sh
gnome-shell --version
uname -r
cat /sys/module/hid_apple/parameters/fnmode
gnome-extensions info apple-fn-lock@thibaudp.github.io
systemctl status apple-fn-lock.service
```

For gesture failures, say whether switching from the menu works. Include relevant service journal errors if present.

## Work on the code

The backend uses Python's standard library plus PyGObject. The extension uses GJS and GNOME Shell's APIs. No npm dependencies or build step are required.

```sh
./scripts/check.sh
python3 scripts/package.py
```

Keep changes scoped and explain the resulting behavior. Add tests for gesture, authorization, persistence, or packaging changes where they catch meaningful failures. Visual changes need a check in a live GNOME session.

Backend files live in `backend/`; extension code and assets in `extension/`; service and authorization configuration in `data/`. Add distributable files to `MANIFEST`.

Install with `./install.sh` to update both the service and extension. For extension-only changes, copy the edited files to your user's extension directory and use the Looking Glass helper documented in the README. GNOME caches imported JavaScript, so simply toggling an extension off and on does not load an edited module.

## Prepare a release

1. Update `VERSION`, `CHANGELOG.md`, and the release notes under `docs/releases/`. GNOME's `extension/metadata.json` uses a separate, monotonically increasing integer version.
2. Run `./scripts/check.sh` and `python3 scripts/package.py`. Check the generated packages from a clean extraction and verify `SHA256SUMS`.
3. Commit and push the changes, then confirm GitHub Actions passed for that exact commit.
4. Create a draft release targeting that commit and attach the versioned source archive, extension ZIP, and `SHA256SUMS`.
5. Review the draft before publishing. Create the final version tag for the verified commit when publishing the release.

The complete source archive is the installation package. The extension ZIP requires the separately installed service and must be described accordingly.

Contributions are provided under the project's [MIT License](LICENSE).
