# gettext-tools lite catalogs

The quality check "msgfmt" reports what `msgfmt -c` would, in the words
of GNU gettext's libgettextpo, which translates them in its
`gettext-tools` domain.

## Why these are copies

Homebrew's gettext and gvsbuild's GTK, which the macOS and Windows
builds bundle libgettextpo from, install no `gettext-tools` catalogs.
So these catalogs are copies of gettext's own translations of the
messages the check reports (`gettext-tools.pot`, 161 of gettext-tools'
messages), and the builds ship them as the whole `gettext-tools`
catalog. Linux uses the distribution's catalogs instead.

Unlike the other lite catalogs, these stay even when gettext translates
every message.

## Translating

Translate gettext-tools upstream, at the Translation Project:
<https://translationproject.org/domain/gettext-tools.html>. Your
translation then reaches every gettext user, and the next refresh below
brings it here.

A translation made only in `<lang>.po` here is kept by the refresh
until gettext has its own, but please send it upstream too.

## Refreshing

From package root, with an unpacked gettext release (its `.version`
names the version):

```sh
python devsupport/pseudo-translation/update_gettext_tools.py ~/src/gettext-1.0
```

This rewrites the template and the catalogs, and the `gettext-tools`
lines of `po/LINGUAS-lite` for the languages in `po/LINGUAS`.
