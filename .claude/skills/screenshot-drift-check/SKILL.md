---
name: screenshot-drift-check
description: Detect and act on the "AppData screenshots are stale" / "Docs screenshots are stale" CI warnings - deliberately non-blocking `::warning::` annotations (issues #3625, #3746) that's easy to miss because it never fails a job or shows up anywhere but a run's ANNOTATIONS list. Load when asked to check CI health/release-readiness, before cutting a release, or periodically to catch drift that's been sitting unnoticed.
---

# Screenshot drift check

Two sets of screenshots are generated and compared against a live render
by the `appdata-screenshots` job in `.github/workflows/ci.yml`:

| Images | Script | Artifact on mismatch | Warning title |
|---|---|---|---|
| `docs/_static/appdata/*.png` (metainfo `raw.githubusercontent.com` URLs) | `generate_appdata_screenshots.py --check` | `appdata-screenshots` | AppData screenshots are stale |
| `docs/_static/*.png` used by `docs/screenshots.rst` | `generate_docs_screenshots.py --check` | `docs-screenshots` | Docs screenshots are stale |

Both scripts live in `devsupport/screenshots/`. See `virtaal-screenshot-automation` memory for the full history.

This check is **intentionally non-blocking** - Dwayne confirmed staleness
here is cosmetic (a stale URL image, not a build break), so the job passes
either way. The only surviving signal on a mismatch is a `::warning::`
annotation:

```
! docs/_static/appdata/*.png no longer match what Virtaal actually renders -
  download the appdata-screenshots artifact from this run and commit the
  refresh.
```

A green run with a buried annotation is functionally invisible unless
something actually goes and looks - that's the gap this skill closes.

## Finding drift

Annotations don't show up in `gh pr checks` or the PR's own UI summary, only
in a run's own detail view:

```
gh run list --workflow=ci.yml --limit 10
gh run view <run-id>          # ANNOTATIONS section, if any
```

Grep across several recent runs at once rather than checking one at a time:

```
for id in $(gh run list --workflow=ci.yml --limit 15 --json databaseId -q '.[].databaseId'); do
  gh run view "$id" 2>/dev/null | grep "no longer match what Virtaal actually renders" | sed "s/^/$id /"
done
```

`gh run view` prints an annotation's message, not its title, so grep for
the message ("no longer match what Virtaal actually renders", shared by
both checks); the printed path says which set is stale. Match on that
text, not a job name - the job that runs
this check has already moved once (from a step inside the `test` job's
python-3.13 leg, to its own `appdata-screenshots` job as of PR #3848) and
may move again.

Quicker per-run signal: the stale-image artifacts are uploaded only on a
mismatch, so their presence alone says which set drifted:

```
gh api repos/translate/virtaal/actions/runs/<run-id>/artifacts -q '.artifacts[].name' | grep screenshots
```

Pass `-R translate/virtaal` to every `gh run` command here - from a fork
checkout `gh` can resolve the default repo to the fork, which has no runs.

Also worth checking on `main` itself, not just open PRs - a merge can
introduce drift that no one's PR-time run caught (e.g. a change to a
different branch that touches rendered UI, merged after the screenshot
check last ran green on that code).

## Fixing drift

This repo commonly has many concurrent worktrees/sessions active (see
`virtaal-heavy-concurrent-sessions` memory) - don't assume the checkout
you're sitting in is free of unrelated WIP. Check `git status`, and if
there's anything on disk you didn't put there, build the fix in a fresh
`git worktree add <scratch-path> -b <branch> upstream/main` instead of
committing into a shared checkout (`shared-checkout-awareness` skill covers
why and how). This also sidesteps `origin/main` being stale relative to
`upstream/main` in a fork+upstream setup.

The workflow already builds the fix artifact - don't regenerate locally,
pull what CI produced:

```
gh run download <run-id> -n appdata-screenshots -D /tmp/appdata-screenshots
cp /tmp/appdata-screenshots/*.png docs/_static/appdata/
git add docs/_static/appdata/*.png
git commit -m "docs: refresh stale AppData screenshots"
```

For the docs set, download `docs-screenshots` and copy into
`docs/_static/`. The artifact holds every docs screenshot, not just the
stale ones - `cmp` each against the committed file and commit only those
that differ.

Before committing, check the render is deterministic: download the same
artifact from two or three recent runs and compare checksums. If they
agree, the committed image is simply out of date; if they don't,
refreshing will just move the warning to the next run.

Before committing, actually *look* at old vs. new side by side (the Read
tool renders a PNG directly; there's no guarantee a system Python here has
Pillow installed for a pixel-diff script) and sanity-check the change looks
like a real UI change (a theme tweak, a scroll/layout shift, a new widget)
rather than a broken capture (blank window, wrong state). `git diff --stat`
on a binary file only reports a byte-size delta, not content - it can't
tell you which of those two this is. The generation script fails hard
(exit 2) on a real error, but a bad crop or timing race that still produces
*a* PNG wouldn't necessarily.

Open this as its own PR/commit rather than folding it into unrelated work in
progress - it's an independent, mechanical refresh.

Name the cause in the commit message: `git log -1 -- docs/_static/<img>`
gives the last refresh date, then `git log --since=<that date> --
virtaal/plugins/<area> virtaal/views` usually turns up the commit that
changed the render (e.g. #4037: autocomplete style from #3917, TM popup
width from c0767f7e). No matching commit is a hint the capture is
nondeterministic - run the checksum comparison above.

A change of a pixel or two is still real drift - zoom the differing
region (crop and upscale both images, side by side) to see what moved
rather than assuming noise.
