"""Validate the packaged TOC and record the exact ZIP identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def inspect_zip(path, name, interface):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, "Corrupt ZIP"
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate ZIP entries"
        for item in names:
            parts = PurePosixPath(item).parts
            assert parts and parts[0] == name and ".." not in parts, f"Unexpected ZIP path: {item}"
            assert not item.startswith("/") and "\\" not in item
            assert not any(x in (".git", ".github", "scripts", "tests", "docs") for x in parts)
        toc = archive.read(f"{name}/{name}.toc").decode("utf-8-sig")
        assert re.search(rf"^## Interface:\s*{interface}\s*$", toc, re.M)
        match = re.search(r"^## Version:\s*(\S+)", toc, re.M)
        assert match and "@" not in match[1], "Unexpanded package version"
        for line in toc.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                assert f"{name}/{line.replace(chr(92), '/')}" in names, f"Missing TOC file: {line}"
        return match[1]


def verify(directory, expected_tag=None):
    metadata = json.loads((directory / "release.json").read_text())
    filename = metadata["filename"]
    assert Path(filename).name == filename and filename.endswith(".zip")
    if expected_tag:
        assert metadata["tag"] == expected_tag, "Manifest tag does not match selected release"
    path = directory / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"], "ZIP checksum mismatch"
    packaged_version = inspect_zip(path, metadata["addon"], metadata["interface"])
    assert packaged_version == metadata["version"], "Manifest and TOC versions differ"
    if expected_tag:
        assert packaged_version.lstrip("v") == expected_tag[1:], "Tag and TOC versions differ"
    return metadata, path


def create():
    cfg = json.loads((ROOT / "addon.json").read_text())
    archives = list((ROOT / ".release").glob("*.zip"))
    assert len(archives) == 1, "Expected exactly one packaged ZIP"
    path = archives[0]
    packaged_version = inspect_zip(path, cfg["name"], cfg["interface"])
    ref = os.environ.get("GITHUB_REF", "")
    tag = ref.removeprefix("refs/tags/") if ref.startswith("refs/tags/") else None
    if tag:
        assert packaged_version.lstrip("v") == tag[1:], "Packager did not use the selected tag"
    metadata = {
        "addon": cfg["name"], "version": packaged_version, "interface": cfg["interface"],
        "tag": tag, "filename": path.name,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (ROOT / ".release/release.json").write_text(json.dumps(metadata, indent=2) + "\n")
    verify(ROOT / ".release", tag)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["create", "verify"])
    args = parser.parse_args()
    if args.mode == "create":
        create()
    else:
        verify(ROOT / ".release", os.environ.get("RELEASE_TAG"))
        print("ZIP checksum, layout, TOC and version verified")
