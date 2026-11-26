"""Upload a checked release artifact using the CurseForge author API.

The default is an offline preview. The workflow sets CF_PUBLISH=1.
No automatic upload retries: investigate ambiguous network failures first.
"""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid

from artifact import ROOT, verify
from check import version

API = "https://wow.curseforge.com/api"


def select_game_version(versions, interface, version_type):
    game_version = f"{interface // 10000}.{interface // 100 % 100}.{interface % 100}"
    matches = [v for v in versions if v["name"] == game_version and v["gameVersionTypeID"] == version_type]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one CurseForge version for {game_version} in flavor {version_type}; refusing fallback")
    return matches[0]["id"]


def release_type(tag):
    version(tag)
    return "alpha" if "-alpha." in tag else "beta" if "-beta." in tag else "release"


def main():
    tag = version(os.environ["RELEASE_TAG"])
    manifest, path = verify(ROOT / ".release", tag)
    cfg = json.loads((ROOT / "addon.json").read_text())
    assert manifest["addon"] == cfg["name"], "Wrong addon's release"
    project = cfg["curseforge_project_id"]
    assert isinstance(project, int) and project > 0, "Set your CurseForge project ID in addon.json"
    preview = {"project": project, "tag": tag, "sha256": manifest["sha256"], "interface": manifest["interface"], "releaseType": release_type(tag)}
    if os.environ.get("CF_PUBLISH") != "1":
        print("Offline upload preview: " + json.dumps(preview, indent=2))
        return
    token = os.environ["CF_API_TOKEN"]
    assert token, "CF_API_TOKEN is empty"
    request = urllib.request.Request(API + "/game/versions", headers={"X-Api-Token": token})
    with urllib.request.urlopen(request, timeout=60) as response:
        versions = json.load(response)
    game_id = select_game_version(versions, manifest["interface"], cfg["curseforge_version_type_id"])
    metadata = {
        "changelog": (ROOT / ".release/notes.md").read_text(),
        "changelogType": "markdown", "displayName": tag,
        "releaseType": release_type(tag), "gameVersions": [game_id],
    }
    boundary = uuid.uuid4().hex
    payload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
        + json.dumps(metadata).encode()
        + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/zip\r\n\r\n'.encode()
        + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        f"{API}/projects/{project}/upload-file", data=payload,
        headers={"X-Api-Token": token, "Content-Type": "multipart/form-data; boundary=" + boundary},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    assert isinstance(result.get("id"), int), "Upload response did not contain a file ID"
    print(f"CurseForge accepted file ID {result['id']} for {tag}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as file:
            file.write(f"CurseForge accepted file **{result['id']}** for **{tag}**. SHA256: `{manifest['sha256']}`.\n")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"CurseForge HTTP {error.code}; inspect project status before retrying") from None
