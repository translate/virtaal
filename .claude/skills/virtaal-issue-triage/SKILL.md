---
name: virtaal-issue-triage
description: How to label and triage Virtaal's GitHub issue backlog - the label taxonomy, platform/l10n inference, and the Bugzilla-import category (unreachable reporters, dead attachment links, and how to verify resolution via git history instead). Load before labeling issues or reviewing/closing old bug reports.
---

# Triaging Virtaal issues

`CHECKLIST-ISSUE.md` (local-only, not committed) has the policy-level
checklist for triaging a single issue - read it first. This skill is
the mechanical/pattern layer underneath it: how to classify at scale
across the backlog, and the one real gotcha (Bugzilla imports) that
CHECKLIST-ISSUE.md doesn't cover.

## Label taxonomy

All labels already exist on `translate/virtaal` - never invent new
ones without checking first (`gh label list --repo translate/virtaal`):

- Type (usually exactly one): `bug`, `enhancement`, `question`,
  `duplicate`, `notabug`, `invalid`.
- `unconfirmed` - not "we don't believe it", but "not verified against
  current code". Add this liberally to old bug reports (see below) -
  it's a statement about verification status, not credibility.
- Platform, when the report is clearly OS-specific: `macos`, `windows`,
  `linux`. Infer from explicit OS mentions, but also from incidental
  detail - "program bar"/"taskbar" phrasing, `.exe` process names, and
  screenshots of Windows chrome are all real Windows signals even when
  the reporter never names the OS.
- `l10n` for anything about translated strings, RTL/bidi rendering,
  language-pair handling, or a translation contribution itself.
- `easyhack` - only apply this yourself if the fix is genuinely obvious
  from reading the report; don't guess optimistically.
- `bugzilla-import` - see below.
- `code smell` (added 2026-09-27) - a complexity/duplication/structural
  finding flagged for investigation, no single fix attached. Covers
  both the manual AST-scan refactor campaign's own issues (#3806,
  #3812) and the automated ruff/pylint findings from the non-blocking
  `code-smell` CI job (#3850).

## Milestone scope

Each milestone's description states its scope - read it
(`gh api repos/translate/virtaal/milestones`) before assigning, and
hold to it literally. Bugfix milestones fill up with anything that
seemed urgent when it was filed; 1.0.1 had drifted to 43 open issues
by 2026-10-03, and only 5 actually fit its scope.

- **1.0.0** - every issue closed by work landed on main before the
  1.0.0 release, whatever milestone it was filed under (1.0.1, 1.1.0,
  Backlog, an old 0.x one). Includes a manual close whose fix landed
  this cycle, or that the py3/GTK3 rewrite or new packaging resolved.
  Not duplicates, questions, notabug, unreproducible, upstream fixes,
  or fixes from years ago.
- **1.0.1** - crashes (including a disabled path that used to
  segfault), installation problems, problems in packaged builds and
  their build tooling, and localisation of Virtaal itself (UI
  language, `--lang`, lite translations, uilang test isolation). It
  stays open until packaged-build signing is in place, so near-misses
  of that scope go here too. Not `l10n`-labelled features for
  translators' own content (TM mnemonics, term capitalisation).
- **1.1.0** - the TM/MT feature cluster and the UI around it.
- **Backlog** - features on the development horizon not tied to TM/MT
  (e.g. #2025, greying out unselectable workflow states), plus dev-only
  behaviour unrelated to localisation, asset automation, and code
  cleanup.

When pruning, the rule Dwayne gave: TM-related or potentially
user-impacting -> 1.1.0, otherwise -> Backlog. A UI feature unrelated
to TM/MT is still Backlog. An issue with an open PR
still moves; the PR is unaffected. A milestone edit is a plain
`gh issue edit <n> --milestone <title>` and needs no comment.

## Old reports and the rewrite

Given the scale of the GTK3/Python 3 rewrite, treat any report against
a pre-1.0 (PyGTK2/Python 2) version as needing fresh verification, not
as still describing current behaviour - `unconfirmed` almost always
belongs alongside the type label for these, even when the report itself
reads as clear and credible.

Read the current code from `upstream/main` (`git show
upstream/main:<path>`), not the local checkout - it is often a feature
branch several commits behind.

## The Bugzilla-import category

Translate ran its own Bugzilla before these were imported to GitHub.
Imported issues are authored by the bot account `transl8bzimport`, not
a real GitHub user - a real, common category (46 of ~269 open issues on
`translate/virtaal` when last counted), not a one-off:

```
gh api graphql -f query='{ repository(owner: "translate", name: "virtaal") { issues(states: OPEN, first: 100, filterBy: {createdBy: "transl8bzimport"}) { nodes { number } } } }' -q '.data.repository.issues.nodes[].number'
```

Two consequences that change how you triage these, confirmed directly
(2026-09-10, translate/virtaal#1175):

1. **There is no reporter to contact.** Can't ask for more info,
   can't confirm a fix resolves their actual case, can't thank them via
   GitHub (no account to @-mention).
2. **Linked attachments/external hosts are very likely dead** (a 2009
   `box.net` link, in one confirmed case) - "the described feature/fix
   already looks present" is not enough to close as resolved/duplicate
   on its own, because there's no way to confirm this report's specific
   case was what actually landed versus something unrelated.

**Don't auto-close a Bugzilla-import issue just because it looks
superseded - but don't leave it unverified either.** Cross-check
against the repo's own history instead of the dead external link:

- For a translation contribution: check the credited translator in the
  relevant `po/<lang>.po` header (`head -30 po/<lang>.po`) against the
  reporter's name in the issue body ("Originally posted by ...") - the
  attribution trail lives in the file, not the issue.
- Either way, find the actual merge commit rather than assuming:
  ```
  git log --all --format="%H %ad %an %s" --date=short --grep="<name or keyword>" -i
  ```
- If confirmed, close citing the real commit hash and message - not a
  generic "fixed" - so the closure is independently verifiable later:
  ```
  gh issue close N --repo translate/virtaal --comment "Merged: <sha> (\"<message>\", <date>)."
  ```
- If you can't confirm either way, leave it open with accurate labels
  rather than guessing - there's no reporter to fall back on if you
  guess wrong.

Label the whole category `bugzilla-import` alongside its normal type/
platform/l10n labels, so it stays visibly distinct from an issue with a
real, contactable reporter.

## Verifying against current code applies beyond Bugzilla imports too

The credit-check/git-log technique above isn't Bugzilla-import-specific
- apply the same "verify, don't assume" bar to any old report that
looks superseded, real reporter or not. Confirmed real closes from a
full sweep of translate/virtaal's backlog (2026-09-10/11), each with
its own concrete evidence, not a guess:

- **A feature genuinely shipped since**: grep the codebase/git log for
  the specific thing asked for (a window-position-persistence request
  closed by pointing at the exact feature now working;
  `git log --grep`, not just "this feels done").
- **A dependency/plugin fully removed**: if the report is scoped to a
  library that's since been dropped entirely (`grep -rl
  <libraryname> virtaal/` returning nothing), the issue no longer
  applies regardless of what it originally asked for - close citing
  the absence, not a fix.
- **A duplicate of a fix landed in the same release cycle**: check
  this session's own recent PRs/RELEASE-BLOCKERS.md before assuming an
  old report is still open - two closures this sweep were reports of
  the exact same bug just fixed hours earlier.
- **Actually reproduce it against current code, live**: for a report
  describing a specific technical failure mode (a parsing bug, a
  round-trip corruption), write the smallest real reproduction against
  current code/dependencies rather than reasoning about whether it
  "sounds fixed" - one confirmed close this sweep was a Unicode/XML
  round-trip bug, verified by actually serializing and re-parsing the
  problem characters through the current library, not by reading the
  fix code and assuming.
- **An asset request (icon/image), by rendering and comparing**: for a
  report asking for an icon/image deliverable, check the actual asset
  tree against the specific thing asked for (sizes present, theme
  directories, format) rather than assuming a same-themed file already
  covers it. Confirmed 2026-09-26, translate/virtaal#748/#1512 (old
  hicolor app-icon requests) - fully satisfied by the current
  `share/icons/hicolor/` tree, closed directly. While checking a
  related "do we have an SVG source" question, a same-motif file
  (`virtaal_logo.svg`, a wordmark logo) looked like a plausible source
  for the app icon glyph at a glance - only rendering both
  (`rsvg-convert`) and comparing images side by side showed they're
  unrelated artwork. Don't infer shared provenance from a shared theme;
  render and look.

In every case, the close comment cites the concrete evidence (a commit,
a grep result, an actual test run) - never a bare "fixed" or "no
longer applicable" with nothing to check it against.

## `gh issue list` silently caps at 30

**Always pass `--limit` explicitly** (500 comfortably covers this
repo's whole open backlog) - without it, `gh issue list` defaults to
30 results, sorted by most-recently-updated, with no warning that
anything was cut off. Confirmed the hard way (2026-09-12): a sweep
believed to cover "all 30 open issues" was actually only the 30
most-recently-touched ones (many touched by this session's own earlier
comments) - the repo actually had 211 open, 89 of them real bug
reports (non-enhancement/question) sitting untouched below that
default page. Get the true count first (`gh issue list --repo
translate/virtaal --state open --limit 500 --json number -q
'length'`) before ever calling a review pass "done" or "the whole
backlog."

## Checking a report that links an external tracker bug

If the report itself links a bug on another project's tracker (a GTK/
GNOME bug for an input-method or rendering issue is common here),
check *that* bug's actual resolution status directly rather than
inferring from "we ported to a newer toolkit version" alone - it's
concrete evidence, not a plausibility argument:

```
curl -sL -A "Mozilla/5.0" "https://bugzilla.gnome.org/show_bug.cgi?id=NNNNNN" \
  | grep -iE "bz_status_|RESOLVED|duplicate"
```

Old GNOME Bugzilla redirects to a banner page for GitLab now, but the
original bug's page still renders below it with real status - resolved
directly, or marked a duplicate of another bug worth checking too (a
confirmed 2026-09-12 case: two separate Virtaal issues, filed years
apart, both root-caused to the same one upstream GTK bug, itself
RESOLVED FIXED - closed both off that single piece of evidence).

## Batch mechanics

Fetching many issue bodies at once (title + body, to actually read
before labeling, not just titles) - GraphQL aliases in one request
beats N separate `gh issue view` calls:

```
NUMS="123 456 789"
Q="{ repository(owner: \"translate\", name: \"virtaal\") {"
for n in ${=NUMS}; do   # zsh: ${=NUMS} forces word-splitting - a bare $NUMS does NOT split in zsh, unlike bash
  Q="$Q i$n: issue(number: $n) { number title body author { login } } "
done
Q="$Q } }"
gh api graphql -f query="$Q"
```

Ranking a batch of unlabeled issues to work through: sort by comment
count (a real, if crude, signal of engagement/severity) - the same
"sampled highest-signal" precedent `ISSUE_TRIAGE.md` already used.

**`gh issue edit --add-label` can fail silently in a loop** - a batch
of ~40 calls had 3 report a generic "failed to update 1 issue" with no
indication of which ones. Re-check the actual label state afterward
rather than trusting the loop's own output:

```
for n in <the numbers you just tried>; do
  gh issue view "$n" --repo translate/virtaal --json labels -q '[.labels[].name] | join(",")'
done
```

and retry whichever came back empty.

**What closed an issue** - a merged PR, a commit, or a manual close -
decides whether it earns a release milestone. The last ClosedEvent's
`closer` says which:

```
gh api graphql -f query='{ repository(owner: "translate", name: "virtaal") { issue(number: N) { timelineItems(itemTypes: [CLOSED_EVENT], last: 1) { nodes { ... on ClosedEvent { closer { __typename ... on PullRequest { number merged } ... on Commit { oid } } } } } } } }'
```

A null `closer` is a manual close: read the closing comment, and check
`git log upstream/main` for when the fix it cites actually landed.

**`gh issue list --milestone` lags a just-made milestone edit** - two
issues edited seconds earlier were missing from the list. Check
`gh issue view N --json milestone` or the milestone's own
`open_issues` count before re-editing.
