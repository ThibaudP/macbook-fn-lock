#!/usr/bin/python3
"""Build redistributable archives without requiring GNOME or root access."""

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def manifest_files(root):
    root = Path(root).resolve()
    files = []
    for line in (root / "MANIFEST").read_text().splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        relative = PurePosixPath(name)
        source = root / relative
        if (relative.is_absolute() or ".." in relative.parts or
                not source.resolve().is_relative_to(root) or source.is_symlink() or
                not source.is_file()):
            raise ValueError(f"Invalid source manifest entry: {name}")
        if relative in files:
            raise ValueError(f"Duplicate source manifest entry: {name}")
        files.append(relative)
    return sorted(files)


def build(root=ROOT, destination=None):
    root = Path(root).resolve()
    version = (root / "VERSION").read_text().strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("VERSION must contain a semantic version such as 0.1.0")
    files = manifest_files(root)
    metadata = json.loads((root / "extension/metadata.json").read_text())
    destination = Path(destination) if destination is not None else root / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    extension_archive = destination / f"{metadata['uuid']}-{version}.zip"
    source_archive = destination / f"macbook-fn-lock-{version}.tar.gz"

    with zipfile.ZipFile(extension_archive, "w") as archive:
        for relative in files:
            if relative.parts[0] == "extension":
                name = relative.relative_to("extension").as_posix()
            elif relative.as_posix() == "data/interface.xml":
                name = "interface.xml"
            elif relative.as_posix() == "LICENSE":
                name = "LICENSE"
            else:
                continue
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, (root / relative).read_bytes(),
                             compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with source_archive.open("wb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for relative in files:
                    source = root / relative
                    info = tarfile.TarInfo(f"macbook-fn-lock-{version}/{relative}")
                    data = source.read_bytes()
                    info.size = len(data)
                    info.mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
                    archive.addfile(info, io.BytesIO(data))

    checksums = destination / "SHA256SUMS"
    checksums.write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted((source_archive, extension_archive))
    ))
    return source_archive, extension_archive, checksums


if __name__ == "__main__":
    for artifact in build():
        print(artifact)
