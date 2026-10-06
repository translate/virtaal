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
rc2 is translations only) to catch up on new strings. When cutting the
final release, exclude the translations below 50% of `virtaal.pot`'s
messages (fuzzy ones don't count; English variants are exempt):

```sh
po/update-linguas.py --cut-off 1.0.0
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
(also updating `LINGUAS-lite`, the lite catalogs that translate
anything, for the languages in `LINGUAS`):

```sh
python devsupport/pseudo-translation/update_lite_catalogs.py gtk30 glib20 gtkspell3 gtk-mac-integration
```
