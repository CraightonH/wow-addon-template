# WoW addon template

A small GitHub template for a WoW Forever addon. It packages with BigWigs Packager and keeps candidate builds, GitHub releases, and CurseForge publication separate. Source and addon tests run before packaging; the generated ZIP is checked before release.

## Create an addon

1. Put this directory in a GitHub repository and enable **Settings → General → Template repository**. Use **Use this template** to create future addon repositories. Templates copy files once; they do not inherit future template fixes.
2. In a new repository, run `python3 scripts/initialize.py YourAddon`. Edit the TOC title, description, author and icon. Keep `@project-version@` as the source version; packaging fills it from Git.
3. Choose a license and add its text as `LICENSE`. Release tag validation requires that file. Choose licenses for your existing addons separately, and retain dependency license notices.
4. Develop in the private `addon` namespace. Store persistent state only in the declared SavedVariables. Add schema migrations as data evolves. Put focused Lua tests under `tests/`.
5. Install Lua 5.1 and run `python3 scripts/check.py`. The CI runner installs Lua automatically. Each branch push and pull request produces a downloadable, validated ZIP under Actions artifacts.

For a local package, install Git, Bash, curl, jq and zip, commit your files, then run the [pinned packager script](https://raw.githubusercontent.com/BigWigsMods/packager/01e8631a69c69d7654c788d152630d5fed9e3812/release.sh) with `bash /path/to/release.sh -d -g forever` from the repository root. Run `python3 scripts/artifact.py create` to validate the result. Do not execute a packager fetched from an unreviewed ref.

## Publish a version

Create the CurseForge project through its author portal and enter the assigned numeric ID as `curseforge_project_id` in `addon.json`. Do not use the IDs of another addon. Add `## X-Curse-Project-ID: YOUR_ID` to the TOC for addon-manager identification. Supply project description, screenshots, icon, support/source links and the chosen license in CurseForge.

Set repository variable `RELEASE_ENABLED=true` to enable GitHub releases. After checks and in-game validation, update `CHANGELOG.md`, commit, and create an **annotated** tag:

```sh
git tag -a v0.1.0-alpha.1 -m 'First public alpha'
git push origin v0.1.0-alpha.1
```

Supported tags are `vX.Y.Z`, `vX.Y.Z-alpha.N` and `vX.Y.Z-beta.N`. The release workflow validates the tag, runs checks and packages once, then creates a GitHub release with that ZIP and `release.json`. Alpha and beta tags become prereleases. Generated GitHub notes use GitHub's comparison of changes; maintain the human changelog for users as well. Never move a published tag to different code; create another version.

Create a GitHub environment named `curseforge`. Add the CurseForge **author upload token** as environment secret `CF_API_TOKEN` and set repository variable `CURSEFORGE_ENABLED=true`. Optionally configure environment reviewers. On the default branch, run **Publish existing release to CurseForge** and enter the exact GitHub release tag. The uploader downloads and checks the original ZIP, then maps its interface to an exact CurseForge game version and Forever type. It fails if the version is absent; it never silently substitutes another version or flavor. API acceptance produces a file ID; site moderation may still be pending.

The uploader defaults to an offline preview when invoked locally. To preview, set a real project ID, put a release ZIP and manifest under `.release/`, and run `RELEASE_TAG=v0.1.0-alpha.1 python3 scripts/publish.py`. Only `CF_PUBLISH=1` enables upload. Do not rerun an upload after an ambiguous network failure until you check whether CurseForge already received it. Concurrency prevents overlapping uploads for the same tag; the CurseForge API does not provide an idempotency key, so sequential reruns can duplicate files.

## Watch client changes

Set repository variable `WATCH_UPSTREAM=true` to enable the daily workflow. GitHub schedules use UTC; execution can be delayed. The monitor reads the community mirror's `forever` branch and its build file at the exact observed commit. The initial baseline in `addon.json` is a research snapshot, **not a claim that your addon was tested on that build**. Set it to a commit matching a client build you have tested.

A new observation opens or updates one compatibility issue and triggers the normal checks and candidate ZIP build. Repeated checks of the same observation do not rebuild or reopen a closed issue. The issue and the `upstream-observation` artifact identify the observed source revision. Candidate tests exercise the addon and mocks, not the new client. Review actual API usage, test in game, then update `reviewed_upstream_commit`. If a run fails after creating the issue, manually run Checks or push the fix; the watcher suppresses that same observation afterward.

The mirror may lag the client and does not expose all server hotfixes or content data. Interface numbers do not change for every build. A new upstream revision does not automatically change a TOC or publish a release. Add a data generator and its own pinned sources only when the addon actually ships generated data.

## Maintain the template

BigWigs Packager is pinned to the verified v2.7.0 commit; Dependabot proposes updates. Review upstream release behavior before updating. GitHub Actions are tracked by their supported major versions. There are no downloaded libraries in this starter. If you add `.pkgmeta` externals, pin them and record their licenses; implement additional validation for their package layout and generated files.

Keep shared CI or release logic in a separately versioned reusable-workflow repository when maintaining several addons becomes repetitive. This starter keeps scripts local so a new addon is understandable on its own.
