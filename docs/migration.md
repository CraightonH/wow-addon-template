# Move existing addons onto the template

Start from a branch or an isolated copy of each existing repository. Preserve history, SavedVariables names, user settings and tests. A template is useful for new repositories; existing addons should adopt the selected files through normal commits.

## LootGoblin

The inspected repository already has pure Lua model/history/betting/integration tests, a Makefile, a reproducible Python ZIP builder, and a GitHub checks workflow testing Lua 5.1 and 5.4. Keep those tests and the reproducible builder if they remain useful. Lua 5.1 is the runtime compatibility baseline; 5.4 is an additional portability check.

Its source layout is `LootGoblin/LootGoblin.toc`. This starter uses a root TOC for BigWigs packaging. Choose one layout deliberately. Either retain the existing builder and add equivalent manifest validation to its ZIP, or move the addon payload to the root and use BigWigs. Do not copy these checks unchanged into a nested source layout.

The inspected source version is `0.9.0-alpha`; the template's release grammar uses numbered prereleases such as `v0.9.0-alpha.1`. Choose the next unused public version and keep existing tags intact. Review the inclusion of Demo.lua and any local development controls before the first public package. Retain the existing test runner rather than replacing it with the starter lifecycle test.

## Rangefinder

The inspected artifact is version `0.1.9`, with Model.lua, Icons.lua, IconCatalog.lua, Range.lua, Options.lua and Core.lua. The deliverable folder is not by itself evidence of the authoritative Git repository. Confirm the source repository before migration.

Bring all payload files and assets into the chosen layout, preserve `RangefinderDB` and `RangefinderCharacterDB`, and add packaging checks without changing runtime behavior. Replace the starter Core.lua and lifecycle test with the actual implementation and its tests. Keep any generated icon catalog together with its generation instructions and source provenance.

## Shared release metadata

Both inspected addons declare interface 16001 and neither inspected TOC declares a CurseForge project ID. Create one CurseForge project per addon and record those IDs separately. Set repository variables and the upload environment per repository. Publish an alpha first and verify its game version, installation layout, settings and update behavior through the actual CurseForge client before a stable release.
