# Reusable addon workflows

The shared workflows and Python release tooling live in this repository. New addons copy the small caller workflows from the template. Existing addons can add the callers and `addon.json` while retaining their own tests, source layout and ZIP builder.

## Version selection

The initial shared release is `workflows-v1.0.0`. Both the workflow's `uses: ...@workflows-v1.0.0` and its `tooling-ref: workflows-v1.0.0` must select the same immutable release. A commit SHA can be used in both places instead. Updating those references adopts shared fixes without copying scripts into the addon. Published shared tags must never be moved; create the next shared version for changes.

## Addon configuration

```json
{
  "name": "LootGoblin",
  "interface": 16001,
  "source_directory": "LootGoblin",
  "artifact_directory": "dist",
  "curseforge_project_id": 1806558,
  "curseforge_version_type_id": 88568
}
```

Use the **new addon's own** project ID. The source and artifact directories default to `.` and `.release` for BigWigs projects. Put the same interface and CurseForge project ID in the source TOC. Each archive must have a single matching addon root, an expanded TOC version, all TOC files and, for releases, `LICENSE`.

`reusable-build.yml` accepts `test-command` and `package-command`. The test command defaults to `python3 scripts/check.py`. Leaving the package command empty uses the pinned BigWigs packager. A custom command builds into the configured artifact directory, which must contain exactly one ZIP. Both Lua 5.1 and 5.4 are installed. Commands are trusted repository configuration and run without publishing secrets.

For release tags, validation exports `ADDON_RELEASE_VERSION` without the `v` prefix. A custom builder must use it for the packaged TOC and filename. It must include the license. Candidate builds may retain their development version. The shared manifest records the package identity, tag, source commit, interface and CurseForge destination.

## Call the build workflow

```yaml
permissions:
  contents: read
jobs:
  checks:
    uses: CraightonH/wow-addon-template/.github/workflows/reusable-build.yml@workflows-v1.0.0
    with:
      tooling-ref: workflows-v1.0.0
      test-command: make test LUA=lua5.1 && make test LUA=lua5.4
      package-command: python3 scripts/package.py
```

Use this under branch-push and pull-request events. Each successful run uploads the validated ZIP and `release.json` as an Actions artifact. Addon tests exercise mocks and pure logic; they do not prove compatibility in the running client.

## Deploy automatically from a tag

```yaml
name: Release and deploy
on:
  push:
    tags: ['v*']
permissions:
  contents: write
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
jobs:
  release:
    uses: CraightonH/wow-addon-template/.github/workflows/reusable-release.yml@workflows-v1.0.0
    with:
      tooling-ref: workflows-v1.0.0
      test-command: make test LUA=lua5.1 && make test LUA=lua5.4
      package-command: python3 scripts/package.py
      publish-curseforge: true
    secrets:
      CF_API_TOKEN: ${{ secrets.CF_API_TOKEN }}
```

Create the `curseforge` environment in the addon repository and add `CF_API_TOKEN` as a repository secret or environment secret. The caller must pass the named secret; nested workflows forward it explicitly. Environment reviewers are optional; leave them unconfigured for automatic deployment. Set `publish-curseforge: false` for GitHub-only releases.

An annotated `vX.Y.Z` tag runs checks, builds once, validates the ZIP, creates a GitHub release and uploads the original archive to CurseForge. `-alpha`, `-alpha.N`, `-beta` and `-beta.N` select the prerelease channel. Alpha/beta GitHub releases are marked prerelease. Unsupported or lightweight tags fail before publication. The source TOC need not be manually bumped when the builder supports the release-version input.

The caller should set workflow concurrency as shown. The deployment workflow additionally serializes uploads per repository/tag. GitHub tag rulesets can restrict who creates release tags if desired. A release tag should point to reviewed, tested source; this workflow does not require it to be on the default branch.

## Recover a failed deploy

`reusable-curseforge.yml` accepts the same tooling version plus a `tag` selecting an existing GitHub release. It checks out that tag's configuration, validates the downloaded manifest and archive against the tag's source commit, and uploads without rebuilding. A caller can expose this through a manual retry workflow, as LootGoblin does.

Successful uploads attach `curseforge-upload.json` to the GitHub release with the CurseForge file ID, project, tag, source commit and ZIP checksum. A matching receipt makes later reruns skip the upload. A conflicting receipt fails. GitHub publication reruns also verify the existing release rather than overwriting its assets.

The upload API has no idempotency key. If the response is lost, or upload succeeds but saving the receipt fails, inspect CurseForge before retrying. Recover a receipt from the accepted file ID and original release manifest, then attach it as `curseforge-upload.json`. Never guess a file ID or delete the receipt to force an upload. No automatic HTTP retry is performed. Site moderation may continue after API acceptance.

## Shared workflow development

Run `python3 -m unittest discover -s shared/tests -v` and Actionlint before tagging a new shared version. Test the template and a custom-builder consumer. Commit changes, create an annotated `workflows-vX.Y.Z` tag and push both. Consumer repositories adopt the new version by changing both references.

The `workflows-` prefix keeps tooling releases separate from addon version tags. The shared Python code is checked out sparsely under `.addon-tooling`; it is excluded from addon packages. Central workflow permissions remain read-only for builds, with Contents write access limited to release/deployment jobs.
