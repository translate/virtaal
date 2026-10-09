# Translations

## Updating translations

From package root:

```sh
make pot
make po/xy.po
```

## Generating the .xml and .desktop files

Ensure that you have gettext installed.

From package root, run:

```sh
./maketranslations
```

This will use the .po files and `.xml.in` and `.desktop.in` to create a
`.xml` and `.desktop` file.

## Which translations ship

`LINGUAS` lists the translations builds include: every `*.po` not in
`LINGUAS-excluded`, so a translation is only left out on purpose, with
the reason on its `LINGUAS-excluded` line. After adding a .po or editing
`LINGUAS-excluded`, from package root:

```sh
po/update-linguas.py
```

pre-commit checks `LINGUAS` against the rule.

Translators get the release candidates (rc1 starts the string freeze,
rc2 is translations only) to catch up on new strings. A final release
ships a translation with all of level 1 (see Translation priorities
below): every core message, and all but 3 of the rest. Before 1.1.0,
translating 50% of `virtaal.pot`'s messages also ships it. Fuzzy
translations don't count, and English variants are exempt. When
cutting the final release, exclude the rest:

```sh
po/update-linguas.py --cut-off 1.0.0
```

To see where each translation stands before then, and the level-1
strings each one still needs - which CI also shows in its job summary:

```sh
po/update-linguas.py --report
```

Translators see the same on [Translate
Virtaal](https://virtaal.translatehouse.org/translate.html), with the
packs to start from. The macOS build writes it with `--progress FILE`,
counting its library gaps, and each main push publishes that to the
`translation-progress` branch, which the page reads.

## Translation priorities

`virtaal.priorities.yaml` gives each message a level, from what Virtaal
shows on screen: level 1 is the welcome screen, menus and editing a
file (with "1" the core: the welcome screen and menus), level 2 settings
and screens seen once, level 3 the rest, and "x" messages translators
are never asked for. A message the file doesn't list is newer than it.
GTK's and the other libraries' messages Virtaal shows are listed too.
`priorities.toml` holds the rules, and explains them. It also defines the
priorities: each is a name with an `order` (lower is more important) and
a `description`, which the generated file lists.

It's made from the same harvest as the lite templates (see below; Linux
needs a real locale such as `LANG=en_US.UTF-8`), in full at each string
freeze:

```sh
python devsupport/pseudo-translation/harvest_sources.py harvest.json
python devsupport/pseudo-translation/generate_priorities.py harvest.json
```

Between string freezes only level 1 and the priorities' definitions
change, with the change that causes it (`--level1-only`). `--check` shows how the file differs from
what Virtaal shows now. CI runs it on every change: when anything
differs, its translation-priorities artifact has the level-1 update to
commit with the change, and the whole file for a string freeze.

### Translation packs

A translation pack is one language's catalog cut down to what users see
most, for a translator to finish first: `<lang>-level1.po` (level 1) and
`<lang>-level2.po` (levels 1 and 2), with the priority file, zipped.
With `--libraries`, it also holds `<domain>-<lang>-level1.po` (and
`-level2`) for GTK and the other libraries, and for language names: only
the messages neither the library's catalog on this host nor its lite
catalog translates. Run that where Virtaal runs:

```sh
po/level-pack.py zu --libraries     # or --all; written to dist/level-packs/
```

CI builds every language's pack on the macOS build (the
translation-packs artifact), and each release candidate has them all as
a release asset. Translators send theirs back zipped, with the
Translation update issue form. To take one back, merge it - only the
messages it translates change. A library one goes into its lite catalog;
then update `LINGUAS-lite` (see Lite versions below):

```sh
po/level-pack.py --merge zu zu-level1.po
po/level-pack.py --merge zu gtk30-zu-level1.po
```

## Lite versions

For languages with no upstream translations of certain packages we
include a 'lite' version. This contains only the strings needed by
Virtaal, nothing more. Translating these will ensure that the user has
an end to end localised experience.

A lite catalog exists only for a language whose upstream catalog doesn't
translate every message in the lite template. It holds every message,
pre-filled with whatever upstream already translates. Once upstream
translates them all, the lite catalog is retired. Ideally you should get
these translations upstreamed.

Builds and dev checkouts merge each lite catalog into the library's own
catalog for that language: upstream's translation wins, and lite only
fills the messages upstream lacks.

Currently we translate lite versions for:

- GTK - <http://l10n.gnome.org/module/gtk+> (scroll down to UI translations)
- gtkspell - <http://translationproject.org/domain/gtkspell.html>
- GLib - <http://l10n.gnome.org/module/glib/>
- gtk-mac-integration (macOS app menu) - <https://l10n.gnome.org/module/gtk-mac-integration/>

The GTK, GLib and gtkspell templates hold what Virtaal really shows,
found by running it under `--pseudo-translation-source`. The macOS app
menu is native, so gtk-mac-integration's template is the fixed list in
`write_lite_templates.py`'s `KEEP` instead. To regenerate them, on each
platform you want covered (Linux needs a real locale such as
`LANG=en_US.UTF-8`, not `C`; gtkspell's menu needs a spelling dictionary
for Afrikaans, the harvest's target language):

```sh
python devsupport/pseudo-translation/harvest_sources.py harvest.json
python devsupport/pseudo-translation/resolve_sources.py harvest.json resolved.json
```

then, with every platform's `resolved.json`:

```sh
python devsupport/pseudo-translation/write_lite_templates.py --merge resolved-*.json
```

and to apply the rule above against the libraries' installed catalogs
(also updating `LINGUAS-lite`, the lite catalogs that fill a gap - translate
a message the library doesn't - for the languages in `LINGUAS`):

```sh
python devsupport/pseudo-translation/update_lite_catalogs.py gtk30 glib20 gtkspell3 gtk-mac-integration
```

To see which library messages each shipped language would still show
in English (neither the library nor a shipped lite catalog translates
them), against this machine's installed catalogs:

```sh
python devsupport/pseudo-translation/report_lite_coverage.py
```

CI runs it after the macOS and Windows builds, against the catalogs
each bundles: a table in the job summary and one non-blocking warning.
To fill a gap, translate `po/lite/<domain>/<lang>.po`.
