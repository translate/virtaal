#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Writes po/lite/gettext-tools/ from an unpacked GNU gettext release:
the template of the messages libgettextpo's checks report, and a
catalog for each of Virtaal's UI languages that gettext translates any
of them in, pre-filled from gettext's own catalog. A translation only
in our catalog is kept where gettext has none. po/LINGUAS-lite lists
the catalogs of the languages Virtaal ships (po/LINGUAS).

    devsupport/pseudo-translation/update_gettext_tools.py ~/src/gettext-1.0

See po/lite/gettext-tools/README.md for why these are copies.
"""

import argparse
import importlib.util
import os
import re
import sys

from translate.misc.multistring import multistring
from translate.storage import pypo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = os.path.join(REPO_ROOT, "po", "lite", "gettext-tools")
LINGUAS = os.path.join(REPO_ROOT, "po", "LINGUAS-lite")
DOMAIN = "gettext-tools"

# The sources of what po_message_check_all() reports: format strings,
# plural forms, newlines and the header.
SOURCES = re.compile(r"format[-.].*|msgl-check\.c|plural-(exp|eval)\.c")
# From msgl-check.c, but never reported: po_message_check_all() checks
# neither accelerators nor compatibility.
UNREPORTED = {
    "msgstr lacks the keyboard accelerator mark '%c'",
    "msgstr has too many keyboard accelerator marks '%c'",
    "plural handling is a GNU gettext extension",
    "memory exhausted",
}


def _lite():
    spec = importlib.util.spec_from_file_location(
        "lite", os.path.join(REPO_ROOT, "virtaal", "support", "libi18n", "lite.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _key(unit):
    context = unit.getcontext()
    prefix = context + "\x04" if context else ""
    if unit.hasplural():
        return prefix + "\0".join(unit.source.strings)
    return prefix + str(unit.source)


def template_units(pot_path):
    """The units of gettext-tools.pot that the checks report."""
    pot = pypo.pofile.parsefile(pot_path)
    units = []
    for unit in pot.units:
        if unit.isheader() or str(unit.source) in UNREPORTED:
            continue
        files = {os.path.basename(location.split(":")[0]) for location in unit.getlocations()}
        if any(SOURCES.fullmatch(f) for f in files):
            units.append(unit)
    return units


def ui_languages():
    """Virtaal's UI languages, without English variants."""
    return sorted(name[:-len(".po")] for name in os.listdir(os.path.join(REPO_ROOT, "po"))
                  if name.endswith(".po") and not name.startswith("en_"))


def _plural_forms(header):
    match = re.search(r"Plural-Forms:[^\n]*", header)
    return match.group(0) if match else None


def write_catalog(path, lang, units, upstream, version):
    existing = {}
    if os.path.isfile(path):
        existing = _lite().read_lite_po(path)

    store = pypo.pofile()
    header = {"Project-Id-Version": "gettext-tools %s" % version,
              "Language": lang,
              "Content-Type": "text/plain; charset=UTF-8",
              "Content-Transfer-Encoding": "8bit"}
    plural_forms = _plural_forms(upstream.get("", "")) or _plural_forms(existing.get("", ""))
    if plural_forms:
        header["Plural-Forms"] = plural_forms.split(":", 1)[1].strip()
    store.updateheader(add=True, **{k.replace("-", "_"): v for k, v in header.items()})

    translated = 0
    for template in units:
        unit = store.addsourceunit(template.source)
        unit.addlocations(template.getlocations())
        for flag in template.typecomments:
            unit.typecomments.append(flag)
        if template.getcontext():
            unit.setcontext(template.getcontext())
        key = _key(template)
        translation = upstream.get(key) or existing.get(key)
        if translation:
            translated += 1
            if template.hasplural():
                unit.target = multistring(translation.split("\0"))
            else:
                unit.target = translation
    with open(path, "wb") as f:
        store.serialize(f)
    return translated


def write_linguas(langs):
    """po/LINGUAS-lite, with this domain's lines for langs."""
    with open(LINGUAS, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f if line.strip() and not line.startswith(DOMAIN + "/")]
    lines += ["%s/%s" % (DOMAIN, lang) for lang in langs]
    with open(LINGUAS, "w", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in sorted(lines)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gettext_dir", help="an unpacked GNU gettext release")
    args = parser.parse_args()

    po_dir = os.path.join(args.gettext_dir, "gettext-tools", "po")
    with open(os.path.join(args.gettext_dir, ".version"), encoding="utf-8") as f:
        version = f.read().strip()
    units = template_units(os.path.join(po_dir, DOMAIN + ".pot"))

    os.makedirs(OUT_DIR, exist_ok=True)
    template = pypo.pofile()
    template.updateheader(add=True, Project_Id_Version="gettext-tools %s" % version,
                          Content_Type="text/plain; charset=UTF-8")
    for unit in units:
        template.addunit(unit)
    with open(os.path.join(OUT_DIR, DOMAIN + ".pot"), "wb") as f:
        template.serialize(f)

    lite = _lite()
    shipped_languages = lite.read_linguas(os.path.join(REPO_ROOT, "po", "LINGUAS"))
    shipped = []
    for lang in ui_languages():
        path = os.path.join(OUT_DIR, lang + ".po")
        gmo = os.path.join(po_dir, lang + ".gmo")
        upstream = lite.read_mo(gmo) if os.path.isfile(gmo) else {}
        if not upstream and not os.path.isfile(path):
            continue
        translated = write_catalog(path, lang, units, upstream, version)
        if not translated:
            os.remove(path)
            continue
        print("%s: %d/%d" % (lang, translated, len(units)))
        if lang in shipped_languages:
            shipped.append(lang)
    write_linguas(shipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
