"""Check source layout and Lua syntax; reject ambiguous release tags."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def version(tag):
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(alpha|beta)\.(0|[1-9][0-9]*))?", tag):
        raise ValueError("Use vX.Y.Z, vX.Y.Z-alpha.N, or vX.Y.Z-beta.N")
    return tag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag-only", action="store_true")
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.version:
        version(args.version)
        return
    if args.tag_only:
        assert (ROOT / "LICENSE").is_file(), "Choose a license and add LICENSE before tagging a release"
        tag = version(os.environ["RELEASE_TAG"])
        kind = subprocess.check_output(["git", "cat-file", "-t", "refs/tags/" + tag], text=True).strip()
        if kind != "tag":
            raise ValueError("Create an annotated tag with git tag -a")
        return
    cfg = json.loads((ROOT / "addon.json").read_text())
    name = cfg["name"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("Addon name must be a Lua identifier")
    toc = (ROOT / (name + ".toc")).read_text()
    assert f"## Interface: {cfg['interface']}\n" in toc, "TOC and addon.json interface differ"
    assert "## Version: @project-version@" in toc, "Version must be assigned by packaging"
    assert f"package-as: {name}\n" in (ROOT / ".pkgmeta").read_text()
    for line in toc.splitlines():
        if line.strip() and not line.startswith("#"):
            file = (ROOT / line.strip().replace("\\", "/")).resolve()
            file.relative_to(ROOT)
            assert file.is_file(), f"Missing TOC file: {line}"
    for file in ROOT.rglob("*.lua"):
        if not any(part in (".git", ".release", ".addon-tooling", ".addon-packager", ".release-artifact") for part in file.parts):
            subprocess.run(["luac5.1", "-p", str(file)], check=True)
    for file in sorted((ROOT / "tests").glob("*.lua")):
        subprocess.run(["lua5.1", str(file)], check=True, cwd=ROOT)
    subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], check=True, cwd=ROOT)
    print("TOC, package name, Lua syntax and addon tests passed")


if __name__ == "__main__":
    main()
