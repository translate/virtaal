---
name: virtaal-release
description: How to cut a Virtaal release (tag push mechanics, pre/post checks, gh-pages and docs upkeep) and what to check first when reviewing release-readiness. Load before pushing a version tag, or when asked to review/update the release checklist/plan docs.
---

# Cutting a Virtaal release

Releases are always cut from `translate/virtaal`, never the fork
(`dwaynebailey/virtaal`) - zero ambiguity, don't ask.

Local planning docs carry the actual current status - read them first,
don't re-derive from scratch:
- `RELEASE-BLOCKERS.md` - per-bug status, what's fixed/deferred/accepted.
- `CHECKLIST-RELEASE.md` - what to confirm before/during/after a release.
- `PLAN-RELEASE-1.0.md` - the overall step sequence and dated decisions.
- `FEATURE-RELEASE-PROCESS.md` - the tag-push mechanics themselves.

All four are `.git/info/exclude`d (local-only, never committed) - keep
them updated in place as things change, and never cite them by name in
a commit message or PR body (same rule as any local `PLAN-*.md`/
`FEATURE-*.md`, see the `commit-style` skill).

## Tag mechanics

Pushing a `v*` tag to `translate/virtaal` triggers `ci.yml`'s `release`
job: it takes the `build-windows-installer`/`build-macos-app` artifacts
already produced by that same commit's CI run (no rebuild), runs
`gh release create` attaching the Windows installer and both macOS
`.dmg`s (arm64/x86_64), and marks pre-release whenever the tag contains
`-beta`/`-rc`/`-alpha`.

**Because it reuses that commit's own CI artifacts rather than
rebuilding, the tagged commit's CI run must already be green before you
tag it** - check the run for `main`'s current tip, not just that the
branch merged:

```
gh run list --repo translate/virtaal --branch main --limit 1 --json status,conclusion,headSha
```

Then tag and push:

```
git tag -a v1.0.0-beta1 <sha> -m "v1.0.0-beta1"
git push upstream v1.0.0-beta1
```

Confirm the release actually landed with all three assets before
telling anyone it shipped:

```
gh release view v1.0.0-beta1 --repo translate/virtaal --json isPrerelease,assets,url -q '{isPrerelease,url,assets:[.assets[].name]}'
```

A real public release/tag push is outward-facing and hard to walk
back - confirm with Dwayne before pushing the tag itself, even if
everything else (CI green, checklist clean) is ready.

## After tagging: things that don't happen automatically

None of these are wired to the tag push - each is a separate, manual
step, easy to forget:

- **`virtaal.translatehouse.org`'s `download.html`** (the `gh-pages`
  branch - a small Jekyll site, entirely separate from the Sphinx docs
  below). Update `_config.yml`'s `latest_version`/`download_url` and
  add a `_posts/<date>-Virtaal-<version>-released.md` post (category
  `releases` - `download.html` pulls the newest one automatically).
  `gh-pages` requires a PR (branch-protected, one required `build`
  check that validates the Jekyll build via `actions/jekyll-build-pages`)
  - no direct pushes.
- **`docs.translatehouse.org`** (Read the Docs, a *different* site -
  built by RTD's own webhook on this repo, not by anything in
  `ci.yml`). Nothing to do here per release, but worth a periodic
  sanity check: RTD's project-level "Default branch" setting doesn't
  follow a GitHub default-branch rename automatically. If it's stuck
  on a deleted branch name, every build fails instantly
  (`commit: null`, `success: false`,
  `curl -s "https://readthedocs.org/api/v3/projects/virtaal/" | jq .default_branch`)
  and the live site silently freezes on whatever build last succeeded.
  Only fixable via the RTD dashboard by one of the project's existing
  maintainers (`gh api repos/translate/virtaal/hooks` shows the
  webhook exists; RTD maintainers aren't GitHub-repo-permission-based,
  check `curl -s ".../projects/virtaal/" | jq .users`).
- **Old release tags matching only the fork, not upstream.** `git tag
  -l` can carry tags (e.g. historical `0.x.y` releases) that only ever
  got pushed to `dwaynebailey/virtaal`, not `translate/virtaal` - diff
  `git ls-remote --tags upstream` against `git ls-remote --tags origin`
  before assuming upstream's tag list is complete.

## Silent vs. public prereleases

Not every tag should get outreach. Check `PLAN-RELEASE-1.0.md`'s own
per-release decision (e.g. beta1 shipped silently - unsigned, no
announcement, purely to exercise the pipeline against real
infrastructure; beta2 is the planned first public one) before doing
translator outreach, opening a feedback window, or updating the
gh-pages download button to point at it - `CHECKLIST-RELEASE.md`'s
Prerelease section gates all of that on this decision explicitly.

## Merge-queue mechanics while landing release-prep PRs

See the `commit-style` skill's "Merge policy" section - a
`--force-with-lease` push silently drops a PR from a GitHub merge
queue, and re-enqueuing needs the new commit's CI to be green first.
