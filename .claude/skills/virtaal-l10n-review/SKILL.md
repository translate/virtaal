---
name: virtaal-l10n-review
description: How to review a translation contribution (a new or updated po/<lang>.po) for validity, coverage, and quality before merging - structural checks, coverage-against-current-pot, spotting a stray/wrong entry and root-causing it, and the abuse/right-to-submit checks a translation PR needs that a code PR doesn't. Load automatically whenever a PR touches po/*.po.
---

# Reviewing a localisation submission

Most reviewers here can't read most of the languages submitted - this
skill is about what's checkable without knowing the language, plus
the handful of things worth spot-checking even so. Run this on every
PR that touches `po/*.po`, without being asked.

## Structural validity

```
msgfmt -c -o /dev/null po/<lang>.po
```

Catches format-string placeholder mismatches (`%s`/`%(name)s` between
msgid and msgstr), broken plural forms, and encoding errors. A real,
hard gate - not just a warning.

## Coverage against the *current* pot, not the file's own header

A submission's `POT-Creation-Date`/location-comment style can look
stale (e.g. intltool-era `../file.py.h` locations, an old
`Project-Id-Version`) without the actual translated *content* being
stale at all - the header just reflects whatever pot snapshot the
contributor's tool last touched, not what got translated. Don't judge
staleness from the header; check real coverage instead:

```
msgmerge --previous po/<lang>.po po/virtaal.pot -o /tmp/merged.po
msgfmt --statistics -o /dev/null /tmp/merged.po
```

Compare the reported count against the pot's own total
(`msgfmt --statistics -o /dev/null po/virtaal.pot`, which reports
everything as "untranslated" - the count is what matters). A
merge that comes back 100% translated with zero fuzzy despite a
years-old-looking header is a genuinely complete submission, not one
that needs re-generating first.

## Same-as-source entries: legitimate vs. a real gap

```python
from translate.storage import pypo
po = pypo.pofile(open('po/<lang>.po', 'rb').read())
same = [u for u in po.units if not u.isheader() and u.source.strip() == u.target.strip() and u.source.strip()]
```

Most hits here are legitimate and expected: URLs, brand/product names
(Mozilla, GNOME, Apertium...), and strings that are pure format
placeholders (`<b>%s</b>`, `Ctrl+%(number_key)d`) - these should stay
identical in every language. Only flag a hit that's real prose
(sentence-length, not a name/placeholder/URL) as a possible skipped
translation.

## Sample real prose for quality

```python
prose = [u for u in po.units if not u.isheader() and len(u.source) > 15
         and u.source.strip() != u.target.strip()
         and not u.source.strip().startswith(('http', 'ftp'))]
import random
for u in random.sample(prose, 20):
    print('EN:', u.source); print('  ->', u.target)
```

Even without reading the language: check that HTML tags (`<b>`,
`<u>`, `<p>`) and printf/named placeholders (`%s`, `%(name)s`) survive
into the translation unchanged, and that the translated length is in
a plausible range for the source (a one-word msgid translated to a
full sentence, or vice versa, is worth asking about).

## Check every URL-valued msgid specifically

```python
urls = [u for u in po.units if u.source.strip().startswith(('http://', 'https://'))]
for u in urls:
    print('=' if u.source.strip() == u.target.strip() else 'DIFFERS', u.source, '->', u.target)
```

A URL msgid's translation should be either identical to the source
(the common case) or a genuinely equivalent localised page - never an
unrelated URL. This is a real, confirmed finding category, not
theoretical (2026-09-22, translate/virtaal#3626): one `DIFFERS` case
turned out to be a completely different, dead old URL, sourced from a
stray translation-memory mismatch during the contributor's own tooling
- worth checking every single one of these by hand since there are
usually only a handful per file.

## Root-causing a wrong-looking entry

Before assuming an odd translation is arbitrary or low-effort, check
for a `#|` previous-msgid comment near it (added by `msgmerge` when a
string's msgid changed since the pot the translator worked from) - it
often explains *exactly* where a stray value came from (a different,
now-renamed string's old translation got carried onto the wrong
entry via a fuzzy/TM match). Root-causing this way turns "this looks
wrong" into a precise, explainable fix rather than a guess.

## Precedent: does the target language actually treat this string as translatable?

Don't assume from first principles (e.g. "acronyms should never be
translated") - check what translators of *this project* have actually
done with the same or similar strings historically:

```
git show upstream/main:po/<lang>.po | grep -A1 '^msgid "<the exact string>"$'
```

Confirmed directly: assumed bare technical acronyms (TMX, INI, RC...)
are never meaningfully translated, generalising from a couple of
examples - checking across all locales turned up real counterexamples
(Zulu's noun-class-prefixed `i-UTX`, Russian's fully-translated `RC` ->
`Файл ресурсов`). The established, existing behaviour of this
project's own translators is the right bar, not a general rule of
thumb about what "should" be translatable.

## Abuse and spam protection

- **Translator's own comments** (if any, in `#.` extracted-comment or
  free-text header lines) should relate to the actual message context
  - a comment that reads as unrelated marketing, links, or spam is a
  real red flag on an otherwise-plausible submission.
- **A submission with mostly-untranslated or machine-garbled content**
  padded out to look complete is worth flagging even if it technically
  passes `msgfmt -c` - the structural checks above catch validity, not
  effort or authenticity.
- **PR title/body and commit message tone** - read them like any other
  contribution for rudeness, spam links, or unrelated content.
- Email in the po header (`Last-Translator: Name <email>`) should be a
  plausible individual address, not an obvious throwaway/bulk pattern.

## Right to submit

- Check whether `po/<lang>.po` already exists and has a credited
  translator (`head -20 po/<lang>.po`) before treating a new
  submission as a fresh, uncontested translation - a competing
  submission for an already-maintained language deserves a heads-up to
  the existing translator, not a silent overwrite.
- If updating an existing file, diff the header's translator credit
  line against what's already there - never let a new PR silently drop
  a previous contributor's `# Name <email>, year` attribution line.
- When a different person submits for a language someone else already
  maintains, @-mention the existing translator on the PR (their email
  is in the current file's header) rather than merging around them -
  they may want to review it, or may already be working on the same
  update themselves.

## Writing up the result

Post the findings as a short note in your own words, not a bulleted
audit-report dump of every check you ran (confirmed 2026-09-22,
#3644: a comment structured as "Structural validity: ... Coverage:
... Attribution: ..." read as a robotic checklist rather than
someone who actually looked at the file). Say what you checked and
what you found in a couple of sentences, the way a human reviewer
would - the checks above are what to *do*, not a template for what to
*write*. Don't announce a merge in the comment ("merging") - that
implies the queue action already happened, and queueing is the
maintainer's own call, not something to promise on their behalf.

## Fixing an issue directly

`maintainerCanModify` (`gh pr view N --json maintainerCanModify`) lets
a maintainer push a fix commit straight onto an external contributor's
PR branch - confirmed working (2026-09-22, #3626) via `git push
<their-fork-url> <local-branch>:<their-branch>`, authenticated through
`git -c credential.helper= -c "credential.https://github.com.helper=!gh auth git-credential" push ...`
rather than extracting a raw token. Still comment explaining the fix
either way.

**Never comment on or push to an external contributor's PR without the
maintainer's explicit go-ahead first** - this applies to l10n
submissions exactly as it does to code PRs (see
`no-unauthorized-external-pr-comments`).
