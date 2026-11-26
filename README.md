# WoW addon template

A GitHub template for WoW Forever addons, backed by versioned reusable build and release workflows. New addons copy the scaffold once; existing addons can adopt the small caller workflows without moving their source or replacing their tests.

## Start an addon

1. Select **Use this template** to create a repository, then run `python3 scripts/initialize.py YourAddon`.
2. Edit the TOC title, description, author and icon. Keep `@project-version@` for BigWigs packaging. Choose a license and add its full text as `LICENSE` before a release.
3. Create a CurseForge project and put its numeric ID in `addon.json` and the TOC's `X-Curse-Project-ID`. Do not reuse another addon's project ID.
4. Add focused Lua tests under `tests/`. Install Lua 5.1 locally and run `python3 scripts/check.py`. Branch pushes and pull requests run checks and upload a validated candidate ZIP.

Source uses the private addon namespace and declared SavedVariables. Add schema migrations when persistent data changes. The client-testing notes are under `docs/`.

## Publish from a tag

Set repository variables `RELEASE_ENABLED=true` and `CURSEFORGE_ENABLED=true`. Create a GitHub environment named `curseforge` and add the CurseForge author upload token as `CF_API_TOKEN`, either as a repository secret or an environment secret. Leave required reviewers unconfigured if deployment should be automatic.

After reviewing and testing the intended source in game, commit it and push an annotated version tag:

```sh
git tag -a v0.1.0-alpha.1 -m 'First public alpha'
git push origin v0.1.0-alpha.1
```

This triggers tests, packaging, archive validation, a GitHub release and a CurseForge upload of the same checked ZIP. The tag supplies the addon version. `vX.Y.Z` is stable; `-alpha`, `-alpha.N`, `-beta` and `-beta.N` select prereleases. The GitHub release includes a manifest and, after successful deployment, a CurseForge upload receipt. Site moderation may still be pending after API acceptance.

The manual **Publish existing release to CurseForge** workflow remains available for deployment recovery without rebuilding. Matching receipts suppress duplicate uploads. For ambiguous upload failures, inspect CurseForge before retrying; the API has no idempotency key.

## Share improvements across addons

The template's caller workflows reference `workflows-v1.0.0`. The shared workflows live in this repository and support both BigWigs and an addon's existing ZIP builder. Their scripts are checked out from the same selected tooling version. Update both the caller's workflow reference and `tooling-ref` to adopt a new shared release; existing addons do not inherit template file edits automatically.

See [reusable workflows](docs/reusable-workflows.md) for configuration, custom builder inputs, automatic deployment, retry behavior and version upgrades. LootGoblin is a custom-builder consumer: it retains its Lua 5.1/5.4 tests and reproducible Python package builder.

## Watch client changes

Set `WATCH_UPSTREAM=true` to enable daily checks of the community UI-source mirror's Forever branch. New observations open or update a compatibility issue and trigger candidate checks. The observation artifact identifies the upstream commit and build. Repeated observations are suppressed, including after closing their issue.

The baseline in `addon.json` is a research snapshot, not a compatibility certification. Replace it with an upstream revision corresponding to a client build you tested. The mirror can lag the client and omits some server-side changes. Monitoring does not change the TOC or publish a release.

## Local development

BigWigs Packager is pinned to v2.7.0. To package locally, commit the source and run the pinned release script with `-d -g forever`; the shared CI workflow performs package and manifest validation automatically. No libraries are bundled by default. Add library pins, license notices and data provenance when needed.

Run shared tooling tests with `python3 -m unittest discover -s shared/tests -v`. Addon tests and watcher tests run through `scripts/check.py`. Dependency updates for GitHub Actions are proposed by Dependabot.
