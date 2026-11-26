"""Observe an upstream revision and maintain one compatibility issue.

Does not change source, interface declarations, tags or releases.
"""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gh(path, method="GET", body=None):
    args = ["gh", "api", "--method", method, path]
    if body is not None:
        args += ["--input", "-"]
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None, text=True, check=True, capture_output=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def observe(cfg):
    upstream = cfg["upstream_repository"]
    branch = urllib.parse.quote(cfg["upstream_branch"], safe="")
    head = gh(f"repos/{upstream}/commits/{branch}")["sha"]
    url = f"https://raw.githubusercontent.com/{upstream}/{head}/version.txt"
    with urllib.request.urlopen(url, timeout=30) as response:
        build = response.read().decode().strip()
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", build), "Unexpected upstream version format"
    return {"repository": upstream, "branch": cfg["upstream_branch"], "commit": head, "build": build}


def main():
    cfg = json.loads((ROOT / "addon.json").read_text())
    data = observe(cfg)
    directory = ROOT / ".release"
    directory.mkdir(exist_ok=True)
    (directory / "upstream.json").write_text(json.dumps(data, indent=2) + "\n")
    baseline = cfg["reviewed_upstream_commit"]
    changed = data["commit"] != baseline
    repo = os.environ["GH_REPO"]
    marker = "<!-- wow-addon-template:forever-compatibility -->"
    title = "Review WoW Forever compatibility"
    # Include closed issues so closing a reviewed observation does not reopen it daily.
    issues = json.loads(subprocess.check_output([
        "gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "1000",
        "--search", '"Review WoW Forever compatibility" in:title', "--json", "number,body,state,title",
    ], text=True))
    issue = next((item for item in issues if item["title"] == title and marker in item["body"]), None)
    revision_marker = f"<!-- upstream-sha:{data['commit']} -->"
    if issue and revision_marker in issue["body"]:
        changed = False
    if changed:
        compare = f"https://github.com/{data['repository']}/compare/{baseline}...{data['commit']}"
        body = f"""{marker}
{revision_marker}
Upstream Forever UI source changed. Build: **{data['build']}**.

[Review the changes]({compare}). Baseline: `{baseline}`. Observed: `{data['commit']}`.

The candidate job checks and packages this addon's current default branch. It does not execute the game client or establish compatibility with this build.

- Inspect API changes used by this addon.
- Run the candidate in the Forever client; test fresh and existing saved data, reload and combat behavior.
- Change the TOC interface only if required and tested.
- Record the tested upstream commit in addon.json, then create a version tag when ready.

Upstream source is a community mirror and can lag the client. No release was published by this check.
"""
        if issue:
            gh(f"repos/{repo}/issues/{issue['number']}", "PATCH", {"body": body, "state": "open"})
        else:
            gh(f"repos/{repo}/issues", "POST", {"title": title, "body": body})
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as file:
            file.write("changed=" + str(changed).lower() + "\n")
    print(json.dumps({**data, "new_review": changed}, indent=2))


if __name__ == "__main__":
    main()
