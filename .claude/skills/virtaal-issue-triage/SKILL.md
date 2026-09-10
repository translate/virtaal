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
