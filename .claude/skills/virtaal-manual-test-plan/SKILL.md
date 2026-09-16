---
name: virtaal-manual-test-plan
description: How a developer and Claude collaboratively test a PR's real GUI behaviour before merge - write a TESTPLAN-<PR#>.md, the developer fills it in live against a running build, Claude triages the findings into fixes. Load before offering to test a PR manually, or when asked to "create a testplan" / "setup for local review" / "cleanup old testplans".
---

# Virtaal manual test plans

Unit tests cover logic; they can't cover "does the right-click menu item
actually appear," "does the dialog actually open focused," or "does Ctrl+Z
actually undo it." For any PR that touches real GUI interaction, this
project's real verification bar is a human clicking through it - not just
green CI. This is the established, repeated workflow for that (used across
PRs #3550, #3547, #3545, and the earlier #3515/#3518/#3540 chain).

## Writing the plan

One file per PR (or PR group): `TESTPLAN-<PR#>.md`, or `TESTPLAN-
<PR#>-<PR#>-...md` for a chain of related PRs tested together in one
session. Root of the repo, **never committed** - it's a personal working
doc, already covered by `.git/info/exclude`'s `/TESTPLAN-*.md` pattern
(added 2026-09-15 after one was accidentally swept into a commit by a bare
`git add -A` - check `git status` before any `-A` add while one of these
exists on disk).

Structure: one `##` section per feature area, one `- [ ]` checkbox per
concrete, single-action thing to try - phrased as an instruction ("Select
a word, right-click it"), not a question. Cover:
- The baseline/existing behaviour the PR shouldn't have regressed, not just
  the new feature itself.
- Edge cases the unit tests can't reach: real mouse clicks vs. programmatic
  selection, empty/whitespace input, very long input (ellipsizing), repeated
  use across multiple units, lifecycle/cleanup (opening a second file,
  toggling the plugin off and on).
- Concrete exact commands where real setup is needed to reach a code path
  (e.g. planting a fake log file, a specific test fixture file to open).

Before writing it, read the PR's actual diff (`git diff upstream/main
<branch>` or `gh pr diff <N>`) rather than just its description - the real
code often reveals edge cases (a regex, a guard clause, a specific error
path) the PR body doesn't mention. Check the existing `test_*.py` file for
what's already unit-tested, so the plan doesn't waste checkboxes
duplicating it.

## Setting up for the test

Check out the PR's branch in the shared working tree (see
`shared-checkout-awareness` first - the developer may already have something
checked out for their own purposes). Run the relevant test suite once as a
baseline before handing it over, and confirm no stray Virtaal process is
already running (`pgrep -fl "bin/virtaal"`).

## While the developer is testing

They fill in the checkboxes themselves (`[x]`/`[ ]`) and add free-text notes
prefixed `RDB:` under any item worth flagging - a finding, a question, or
just an observation ("hard to find between-word whitespace to click on").
**Don't edit the file while they're actively using it** - a `<system-reminder>`
noting it changed on disk mid-session means it's their edit, not a sign of a
sync problem. Wait for an explicit "testplan completed" or similar before
triaging.

## Triaging results

Once they say it's done, read through every `RDB:` note. Not all of them
are bugs - some are questions, some are confirmations ("yep, works").
Investigate each concrete failure with the same rigor as any other bug
report (find root cause, don't guess) before proposing a fix - see this
project's own commit-style/verification-bar conventions for how fixes then
get committed and tested.

## Cleaning up

Once the PR is merged, or queued for merge with nothing further expected
from that round, the test plan has served its purpose - delete it (per
an explicit "cleanup any testplans now complete" instruction, 2026-09-15).
Don't delete one that's still mid-review or has unresolved
`RDB:` items still being worked through, even if some PRs it covers have
already merged (e.g. `TESTPLAN-3515-3518-3540.md` stayed even after
#3518/#3540 merged, because #3515's own findings were still open).
