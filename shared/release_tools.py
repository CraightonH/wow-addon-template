"""Shared addon release operations. Run from the caller repository root.

No upload retries: a lost HTTP response can conceal a successful upload.
Successful uploads get a receipt attached to the GitHub release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

ROOT = Path.cwd()
API = "https://wow.curseforge.com/api"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tag_version(tag):
    number = r"(?:0|[1-9][0-9]*)"
    require(re.fullmatch(rf"v{number}\.{number}\.{number}(?:-(?:alpha|beta)(?:\.{number})?)?", tag),
            "Use vX.Y.Z, vX.Y.Z-alpha[.N], or vX.Y.Z-beta[.N]")
    return tag[1:]


def channel(tag):
    tag_version(tag)
    return "alpha" if "-alpha" in tag else "beta" if "-beta" in tag else "release"


def local_path(root, value, allow_root=True):
    path = (root / value).resolve()
    require(not Path(value).is_absolute() and path.is_relative_to(root.resolve()), "Path escapes repository")
    require(allow_root or path != root.resolve(), "Artifact directory cannot be the repository root")
    return path


def config(root):
    cfg = json.loads((root / "addon.json").read_text())
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", cfg["name"]), "Invalid addon name")
    require(type(cfg["interface"]) is int and cfg["interface"] > 0, "Invalid interface")
    require(type(cfg["curseforge_project_id"]) is int and cfg["curseforge_project_id"] >= 0, "Invalid project ID")
    require(type(cfg["curseforge_version_type_id"]) is int and cfg["curseforge_version_type_id"] > 0, "Invalid game flavor ID")
    source = local_path(root, cfg.get("source_directory", "."))
    directory = local_path(root, cfg.get("artifact_directory", ".release"), allow_root=False)
    return cfg, source, directory


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def emit(file_variable, name, value):
    file = os.environ.get(file_variable)
    if file:
        with open(file, "a") as stream:
            stream.write(f"{name}={value}\n")


def prepare():
    cfg, source, directory = config(ROOT)
    toc = (source / (cfg["name"] + ".toc")).read_text()
    require(re.search(rf"^## Interface:\s*{cfg['interface']}\s*$", toc, re.M), "TOC interface differs from addon.json")
    if cfg["curseforge_project_id"]:
        require(re.search(rf"^## X-Curse-Project-ID:\s*{cfg['curseforge_project_id']}\s*$", toc, re.M), "TOC CurseForge project ID differs from addon.json")
    tag = os.environ.get("RELEASE_TAG", "")
    if tag:
        version = tag_version(tag)
        require((ROOT / "LICENSE").is_file(), "Add the chosen LICENSE before releasing")
        require(git("cat-file", "-t", "refs/tags/" + tag) == "tag", "Release tags must be annotated: git tag -a")
        require(git("rev-parse", "refs/tags/" + tag + "^{commit}") == git("rev-parse", "HEAD"), "Checked-out commit does not match release tag")
        emit("GITHUB_ENV", "ADDON_RELEASE_VERSION", version)
    emit("GITHUB_OUTPUT", "artifact-directory", directory.relative_to(ROOT).as_posix())
    emit("GITHUB_OUTPUT", "artifact-name", "addon-" + git("rev-parse", "HEAD"))
    print(f"Validated configuration for {cfg['name']} ({tag or 'candidate'})")


def inspect_zip(path, name, interface):
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "Corrupt archive")
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate archive members")
        for item in names:
            parts = PurePosixPath(item).parts
            require(parts and parts[0] == name and ".." not in parts and not item.startswith("/") and "\\" not in item, "Unexpected archive path: " + item)
            require(not any(p in (".git", ".github", "scripts", "tests", "docs", ".addon-tooling") for p in parts), "Development files in archive")
            require((archive.getinfo(item).external_attr >> 16) & 0o170000 != 0o120000, "Symlinks are not allowed in archive")
        toc = archive.read(f"{name}/{name}.toc").decode("utf-8-sig")
        require(re.search(rf"^## Interface:\s*{interface}\s*$", toc, re.M), "Packaged interface mismatch")
        match = re.search(r"^## Version:\s*(\S+)", toc, re.M)
        require(match and "@" not in match[1], "Missing or unexpanded package version")
        for line in toc.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                require(f"{name}/{line.replace(chr(92), '/')}" in names, "Missing TOC dependency: " + line)
        return match[1], names


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    cfg, _, directory = config(ROOT)
    archives = list(directory.glob("*.zip"))
    require(len(archives) == 1, "Expected exactly one built ZIP")
    path = archives[0]
    version, names = inspect_zip(path, cfg["name"], cfg["interface"])
    tag = os.environ.get("RELEASE_TAG") or None
    if tag:
        require(version.removeprefix("v") == tag_version(tag), "Package version does not match tag")
        require(f"{cfg['name']}/LICENSE" in names, "Release ZIP must include LICENSE")
    data = {
        "addon": cfg["name"], "interface": cfg["interface"], "version": version,
        "tag": tag, "source_commit": git("rev-parse", "HEAD"),
        "filename": path.name, "sha256": digest(path),
        "curseforge_project_id": cfg["curseforge_project_id"],
        "curseforge_version_type_id": cfg["curseforge_version_type_id"],
    }
    (directory / "release.json").write_text(json.dumps(data, indent=2) + "\n")
    verify(directory, tag, cfg)
    print(json.dumps(data, indent=2))


def verify(directory, tag, cfg, source_commit=None):
    data = json.loads((directory / "release.json").read_text())
    require(re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", data["filename"]), "Unsafe artifact filename")
    for field, key in [("addon", "name"), ("interface", "interface"), ("curseforge_project_id", "curseforge_project_id"), ("curseforge_version_type_id", "curseforge_version_type_id")]:
        require(data[field] == cfg[key], "Manifest configuration mismatch: " + key)
    if tag:
        require(data["tag"] == tag and data["version"].removeprefix("v") == tag_version(tag), "Manifest/tag mismatch")
    if source_commit:
        require(data["source_commit"] == source_commit, "Manifest source commit mismatch")
    path = directory / data["filename"]
    require(digest(path) == data["sha256"], "Artifact checksum mismatch")
    version, names = inspect_zip(path, data["addon"], data["interface"])
    require(version == data["version"], "Manifest/TOC version mismatch")
    if tag:
        require(f"{data['addon']}/LICENSE" in names, "Release ZIP must include LICENSE")
    return data, path


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True).strip()


def existing_release(tag):
    repo = os.environ["GH_REPO"]
    result = subprocess.run(["gh", "api", f"repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}"], text=True, capture_output=True)
    if result.returncode:
        if "HTTP 404" in result.stderr:
            return None
        raise RuntimeError("Unable to inspect GitHub release: " + result.stderr)
    return json.loads(result.stdout)


def download(tag, filename, directory):
    gh("release", "download", tag, "--pattern", filename, "--dir", str(directory))


def publish_github():
    cfg, _, _ = config(ROOT)
    tag = os.environ["RELEASE_TAG"]
    data, path = verify(ROOT / ".release-artifact", tag, cfg, git("rev-parse", "HEAD"))
    existing = existing_release(tag)
    if existing:
        # Re-running failed deployment jobs must preserve the already published bytes.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            download(tag, "release.json", directory)
            download(tag, data["filename"], directory)
            other, _ = verify(directory, tag, cfg, data["source_commit"])
            require(other == data, "Existing GitHub release differs; publish a new version")
        print("Existing GitHub release verified; continuing deployment")
        return
    args = ["release", "create", tag, "--verify-tag", "--title", tag, "--generate-notes"]
    if channel(tag) != "release":
        args.append("--prerelease")
    gh(*args, str(path), str(path.parent / "release.json"))


def select_game_version(versions, interface, flavor):
    name = f"{interface // 10000}.{interface // 100 % 100}.{interface % 100}"
    matches = [item for item in versions if item["name"] == name and item["gameVersionTypeID"] == flavor]
    require(len(matches) == 1, f"No unique exact CurseForge game version for {name}, flavor {flavor}; refusing fallback")
    return matches[0]["id"]


def upload_cf(data, path, notes, token):
    request = urllib.request.Request(API + "/game/versions", headers={"X-Api-Token": token})
    with urllib.request.urlopen(request, timeout=45) as response:
        versions = json.load(response)
    game_id = select_game_version(versions, data["interface"], data["curseforge_version_type_id"])
    metadata = {"changelog": notes, "changelogType": "markdown", "displayName": data["tag"], "releaseType": channel(data["tag"]), "gameVersions": [game_id]}
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
            + json.dumps(metadata).encode()
            + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/zip\r\n\r\n'.encode()
            + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(f"{API}/projects/{data['curseforge_project_id']}/upload-file", data=body,
                                     headers={"X-Api-Token": token, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.load(response)
    require(type(result.get("id")) is int and result["id"] > 0, "Upload response missing file ID; inspect CurseForge before retrying")
    return result["id"]


def receipt_matches(receipt, data):
    return (type(receipt.get("file_id")) is int and receipt["file_id"] > 0
            and all(receipt.get(key) == data[key] for key in ("tag", "sha256", "source_commit", "curseforge_project_id")))


def publish_curseforge():
    cfg, _, _ = config(ROOT)
    tag = os.environ["RELEASE_TAG"]
    tag_version(tag)
    require(cfg["curseforge_project_id"] > 0, "Set curseforge_project_id in addon.json")
    existing = existing_release(tag)
    require(existing is not None and not existing["draft"], "Expected an existing published GitHub release")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        download(tag, "release.json", directory)
        # Read only the filename until verify() authenticates layout and identity.
        filename = json.loads((directory / "release.json").read_text())["filename"]
        require(re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", filename), "Unsafe artifact filename")
        download(tag, filename, directory)
        data, path = verify(directory, tag, cfg, git("rev-parse", "HEAD"))
        receipt_name = "curseforge-upload.json"
        if any(asset["name"] == receipt_name for asset in existing["assets"]):
            download(tag, receipt_name, directory)
            receipt = json.loads((directory / receipt_name).read_text())
            require(receipt_matches(receipt, data), "Existing CurseForge upload receipt differs; investigate before retrying")
            print(f"Already uploaded as CurseForge file {receipt['file_id']}; skipping")
            return
        token = os.environ.get("CF_API_TOKEN", "")
        require(token, "Add CF_API_TOKEN as a repository secret or curseforge environment secret")
        file_id = upload_cf(data, path, existing.get("body") or "", token)
        receipt = {key: data[key] for key in ("tag", "sha256", "source_commit", "curseforge_project_id")}
        receipt["file_id"] = file_id
        (directory / receipt_name).write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"CurseForge accepted file ID {file_id}")
        # Preserve a durable receipt so ordinary deployment reruns do not duplicate uploads.
        # If this fails, recover the receipt before retrying the upload job.
        gh("release", "upload", tag, str(directory / receipt_name))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as stream:
                stream.write(f"CurseForge accepted **{tag}**, file **{file_id}**. SHA256 `{data['sha256']}`.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "manifest", "github", "curseforge"])
    args = parser.parse_args()
    {"prepare": prepare, "manifest": manifest, "github": publish_github, "curseforge": publish_curseforge}[args.command]()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, urllib.error.URLError) as error:
        raise SystemExit(str(error) + "\nFor ambiguous upload failures, inspect CurseForge and restore the receipt before retrying.") from None
