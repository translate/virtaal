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

## Old reports and the rewrite

Given the scale of the GTK3/Python 3 rewrite, treat any report against
a pre-1.0 (PyGTK2/Python 2) version as needing fresh verification, not
as still describing current behaviour - `unconfirmed` almost always
belongs alongside the type label for these, even when the report itself
reads as clear and credible.

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
