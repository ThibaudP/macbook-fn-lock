#!/usr/bin/python3
"""Build redistributable archives without requiring GNOME or root access."""

from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
UUID = "apple-fn-lock@thibaudp.github.io"

with zipfile.ZipFile(DIST / f"{UUID}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((ROOT / "extension").iterdir()):
        if path.is_file():
            archive.write(path, path.name)
    archive.write(ROOT / "data/interface.xml", "interface.xml")
    archive.write(ROOT / "LICENSE", "LICENSE")

with tarfile.open(DIST / "macbook-fn-lock.tar.gz", "w:gz") as archive:
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in {".git", "dist", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        if path.is_file():
            archive.add(path, arcname=Path("macbook-fn-lock") / relative)

print(f"Created archives in {DIST}")
