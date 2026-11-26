# Adopt shared workflows in an existing addon

Keep the existing repository history, source layout, SavedVariables names and tests. Add the caller workflows, the three local reusable workflow entry points, and addon.json through normal commits. GitHub template files are a scaffold, not an ongoing inheritance relationship.

## LootGoblins

The GitHub repository was retrofitted at source version 0.3.1-alpha. Its existing model, history and integration tests continue to run on Lua 5.1 and 5.4. The original deterministic ZIP builder is retained and now accepts ADDON_RELEASE_VERSION for the packaged TOC and filename, includes LICENSE, and leaves tracked source unchanged.

Its addon.json declares the nested LootGoblins source directory and dist artifact directory. Shared build validation checks the resulting archive and records its checksum, tag, source commit and CurseForge destination. Annotated version tags automatically create a GitHub release and upload the same archive to project 1806558. See the addon repository's docs/releases.md for release and recovery commands.

A separate, newer local working copy existed during the initial research. It was not merged into the GitHub repository as part of this tooling retrofit. A tag releases the source commit it points to.

## Rangefinder and future addons

Confirm the authoritative source repository first. Preserve RangefinderDB and RangefinderCharacterDB when migrating Rangefinder. Add addon.json with its own CurseForge project ID, source directory and artifact directory. Copy the caller examples and `reusable-build.yml`, `reusable-release.yml`, and `reusable-curseforge.yml` from the same selected template version, as described in reusable-workflows.md and supply the existing test and package commands.

A custom builder must write exactly one ZIP in a clean artifact directory and use ADDON_RELEASE_VERSION for a tagged build. The ZIP needs a matching addon folder/TOC, included dependencies and license. Keep generated icon/data catalogs with their generation instructions and provenance. Add packaging tests that verify versions, payloads and preservation of source files.

## Shared release versions

Use the same version or SHA for remote uses references and tooling-ref, and refresh the local reusable workflow copies from that version. Release and manual retry callers use local paths. New shared tooling versions are adopted by updating those references; no shared Python scripts need to be copied into consumer repositories. Run branch CI before tagging an addon release, and test the packaged addon in game before declaring compatibility.
