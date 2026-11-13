import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        for relative in package.manifest_files(ROOT):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        self.prefix = f"macbook-fn-lock-{(self.root / 'VERSION').read_text().strip()}"

    def test_source_excludes_unlisted_files_and_preserves_installers(self):
        (self.root / ".env").write_text("LOCAL_ONLY=do-not-distribute\n")
        (self.root / "backend/local-notes.txt").write_text("local notes")
        source, _extension, _checksums = package.build(self.root)
        with tarfile.open(source) as archive:
            names = archive.getnames()
            self.assertFalse(any(".env" in name or "local-notes" in name for name in names))
            self.assertTrue(archive.getmember(f"{self.prefix}/install.sh").mode & 0o111)
            self.assertTrue(archive.getmember(f"{self.prefix}/uninstall.sh").mode & 0o111)
            self.assertIn(f"{self.prefix}/scripts/reload-in-shell.js", names)

    def test_extension_includes_assets_shared_interface_and_license(self):
        _source, extension, _checksums = package.build(self.root)
        with zipfile.ZipFile(extension) as archive:
            self.assertEqual(set(archive.namelist()), {
                "extension.js", "metadata.json", "stylesheet.css", "fn-key-symbolic.svg",
                "interface.xml", "LICENSE",
            })
            metadata = json.loads(archive.read("metadata.json"))
            self.assertEqual(metadata["uuid"], "apple-fn-lock@thibaudp.github.io")
            self.assertEqual(archive.read("interface.xml"), (self.root / "data/interface.xml").read_bytes())

    def test_checksums_cover_both_archives(self):
        source, extension, checksums = package.build(self.root)
        lines = checksums.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        for path in (source, extension):
            self.assertIn(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}", lines)

    def test_packages_are_reproducible_despite_local_mtimes(self):
        artifacts = package.build(self.root)
        initial = {path.name: path.read_bytes() for path in artifacts}
        for path in self.root.rglob("*"):
            if path.is_file() and "dist" not in path.parts:
                os.utime(path, (1_700_000_000, 1_700_000_000))
        rebuilt = package.build(self.root)
        self.assertEqual(initial, {path.name: path.read_bytes() for path in rebuilt})

    def test_manifest_rejects_source_symlinks(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("not part of this project")
        (self.root / "external.txt").symlink_to(outside)
        with (self.root / "MANIFEST").open("a") as output:
            output.write("\nexternal.txt\n")
        with self.assertRaises(ValueError):
            package.build(self.root)


if __name__ == "__main__":
    unittest.main()
