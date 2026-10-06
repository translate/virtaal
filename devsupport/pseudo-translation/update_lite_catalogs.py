#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Applies the lite catalog rule to po/lite/<domain>/, for each of
Virtaal's UI languages (po/*.po):

- the library's own installed catalog translates every message in the
  lite template: no lite catalog, an existing one is removed;
- otherwise: a lite catalog with every template message, each keeping
  its lite translation, else taking the library's own.

A lite catalog is merged into the library's own when shipped, the
library's translation winning, so only its gaps take effect; the
pre-filled messages cover a build host with an older library catalog.
po/LINGUAS-lite lists the lite catalogs that translate anything, for
the languages Virtaal ships (po/LINGUAS, see po/update-linguas.py);
the others' lite catalogs are kept for when their translation ships.
"""

import argparse
import gettext
import importlib.util
import os
import sys

from translate.lang import factory as lang_factory
from translate.misc.multistring import multistring
from translate.storage import factory, pypo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
LITE_DIR = os.path.join(REPO_ROOT, "po", "lite")
LINGUAS = os.path.join(REPO_ROOT, "po", "LINGUAS-lite")
SHIPPED = os.path.join(REPO_ROOT, "po", "LINGUAS")


def _generator():
    spec = importlib.util.spec_from_file_location(
        "generate_pseudo_translation", os.path.join(HERE, "generate_pseudo_translation.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ui_languages():
    """Virtaal's UI languages, without English variants: the libraries'
        messages are already English."""
    return sorted(name[:-len(".po")] for name in os.listdir(os.path.join(REPO_ROOT, "po"))
                  if name.endswith(".po") and not name.startswith("en_"))


def shipped_languages():
    """The languages Virtaal ships its own translation for (po/LINGUAS)."""
    with open(SHIPPED, encoding="utf-8") as f:
        return set(f.read().split())


def _key(unit):
    return (unit.getcontext() or "", str(unit.source))


def _translations(store):
    """{(context, msgid): target} of a store's translated messages."""
    return {_key(unit): unit.target for unit in store.units
            if not unit.isheader() and unit.istranslated()}


def upstream_translations(domain, lang, upstream_dir):
    """The library's own translations for lang - its exact catalog, else
        its language's, as gettext looks them up - or {}."""
    path = gettext.find(domain, upstream_dir, [lang]) if upstream_dir else None
    if not path:
        return {}
    # Python's own reader: translate's can't read revision 1 .mo files
    # (GTK's).
    with open(path, "rb") as f:
        catalog = gettext.GNUTranslations(f)._catalog
    translations, plurals = {}, {}
    for key, target in catalog.items():
        if isinstance(key, tuple):
            key, form = key
            plurals.setdefault(key, {})[form] = target
        elif key and target:
            translations[key] = target
    for key, forms in plurals.items():
        if all(forms.values()):
            translations[key] = multistring([forms[i] for i in sorted(forms)])
    return {tuple(key.rpartition("\x04")[::2]): target for key, target in translations.items()}


def _new_catalog(lang):
    store = pypo.pofile()
    language = lang_factory.getlanguage(lang)
    store.updateheader(add=True, Language=lang, Content_Type="text/plain; charset=UTF-8",
                       Plural_Forms="nplurals=%d; plural=%s;" % (language.nplurals, language.pluralequation))
    return store


def update(domain, lang, upstream):
    """Applies the rule to po/lite/<domain>/<lang>.po given the library's
        own translations; returns how many messages it translates (0 when
        it isn't needed)."""
    template = factory.getobject(os.path.join(LITE_DIR, domain, domain + ".pot"))
    messages = [unit for unit in template.units if not unit.isheader()]
    path = os.path.join(LITE_DIR, domain, lang + ".po")

    if all(_key(unit) in upstream for unit in messages):
        if os.path.exists(path):
            os.remove(path)
        return 0

    existing = factory.getobject(path) if os.path.exists(path) else None
    lite = _translations(existing) if existing else {}
    previous = {_key(unit): unit for unit in existing.units
                if not unit.isheader() and not unit.isobsolete()} if existing else {}
    store = _new_catalog(lang)
    if existing and existing.header():
        store.units = [existing.header()]
    translated = 0
    for message in messages:
        unit = store.addsourceunit(message.source)
        unit.setcontext(message.getcontext())
        if message.getnotes("developer"):
            unit.addnote(message.getnotes("developer"), origin="developer")
        before = previous.get(_key(message))
        if before is not None and before.getnotes("translator"):
            unit.addnote(before.getnotes("translator"), origin="translator")
        target = lite.get(_key(message)) or upstream.get(_key(message))
        if target:
            unit.target = target
            translated += 1
        elif before is not None and before.isfuzzy() and before.target:
            # Unfinished work: kept, still fuzzy, so it doesn't ship.
            unit.target = before.target
            unit.markfuzzy()
    if existing:
        store.units.extend(unit for unit in existing.units if unit.isobsolete())
    with open(path, "wb") as f:
        store.serialize(f)
    return translated


def write_linguas(shipped):
    """po/LINGUAS-lite: other domains' lines as they are, these domains'
        from shipped ({domain: [lang, ...]})."""
    with open(LINGUAS, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    lines = [line for line in lines if line.split("/")[0] not in shipped]
    lines += ["%s/%s" % (domain, lang) for domain, langs in shipped.items() for lang in langs]
    with open(LINGUAS, "w", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in sorted(lines)))


def main():
    generator = _generator()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domains", nargs="+",
                        choices=[d for d in generator.LIBRARY_SOURCES if os.path.isdir(os.path.join(LITE_DIR, d))])
    args = parser.parse_args()

    shipped, languages = {}, shipped_languages()
    for domain in args.domains:
        upstream_dir = generator.library_locale_dir(generator.LIBRARY_SOURCES[domain][1])
        if upstream_dir is None:
            sys.exit("%s isn't installed - can't read its own translations" % domain)
        shipped[domain] = []
        for lang in ui_languages():
            translated = update(domain, lang, upstream_translations(domain, lang, upstream_dir))
            if translated and lang in languages:
                shipped[domain].append(lang)
        print("%s: %d lite catalogs translate something (upstream: %s)"
              % (domain, len(shipped[domain]), upstream_dir))
    write_linguas(shipped)


if __name__ == "__main__":
    main()
