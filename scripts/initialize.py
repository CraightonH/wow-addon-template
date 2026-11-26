"""Rename the starter once; run before importing existing addon files."""
import argparse
import json
import re

from artifact import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("name", help="Addon folder name and Lua identifier, e.g. MyAddon")
args = parser.parse_args()
if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", args.name):
    parser.error("Use a Lua identifier beginning with a letter")
cfg = json.loads((ROOT / "addon.json").read_text())
if cfg["name"] != "ExampleAddon":
    parser.error("This template has already been initialized")
for file in [ROOT / "ExampleAddon.toc", ROOT / "Core.lua", ROOT / ".pkgmeta", ROOT / "addon.json"]:
    file.write_text(file.read_text().replace("ExampleAddon", args.name))
(ROOT / "ExampleAddon.toc").rename(ROOT / (args.name + ".toc"))
print(f"Initialized {args.name}. Set project metadata and choose a license before publishing.")
