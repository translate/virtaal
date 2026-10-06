#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Rewrites po/lite/<domain>/<domain>.pot from resolve_sources.py's
output: the GTK, GLib and gtkspell messages Virtaal really shows, each with where
it was seen. With --merge, also updates each po/lite/<domain>/*.po to
the new template.

Left out: messages only seen in GTK's own file chooser (Windows and
macOS show the OS's file dialog, and Linux uses the distro's
translations) or in a font button's placeholder. Always kept: KEEP
below, messages no harvest can see.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

from translate.misc.multistring import multistring
from translate.storage import factory, pypo

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LITE_DIR = os.path.join(REPO_ROOT, "po", "lite")
DOMAINS = ("gtk30", "glib20", "gtkspell3", "gtk-mac-integration")
EXCLUDED_WITHIN = {"FileChooser", "FontButton"}
KEEP = {
    # The UI's text direction - a right-to-left language translates it
    # to default:RTL.
    "gtk30": ["default:LTR",
              # The recent files menu numbers its first ten items with a
              # mnemonic, the rest without.
              "recent menu label\x04_%d. %s", "recent menu label\x04%d. %s"],
    # GLib.format_size() in Properties: a harvest only sees one file
    # size's unit.
    "glib20": ["byte\0bytes", "format-size\x04%u %s", "format-size\x04%.1f\xa0%s",
               "kB", "MB", "GB", "TB", "PB", "EB"],
    # The spelling menu's items depend on the word: suggestions, too many
    # suggestions, or none.
    "gtkspell3": ["<i>(no suggestions)</i>", 'Add "%s" to Dictionary', "Ignore All", "More..."],
    # The macOS app menu is native, so no harvest sees it. Virtaal sets
    # no Window menu, so Window, Minimize and Bring All to Front never
    # show; About %s labels Virtaal's own About item.
    "gtk-mac-integration": ["About %s", "Services", "Hide %s", "Hide Others", "Show All", "Quit %s"],
}
WITHIN_NAMES = {"Menu": "menus", "AboutDialog": "About dialog",
                "ShortcutsWindow": "Keyboard Shortcuts window"}
TAG_RE = re.compile(r"(?:vt|gtk|glib|iso|spell|mac)!?:")
WINDOW_RE = re.compile(r"^(\w+) (?:'(.*)'|None)$")


def _place(within, window):
    if within in WITHIN_NAMES:
        return WITHIN_NAMES[within]
    match = WINDOW_RE.match(window)
    if match is None:
        return None
    kind, title = match.groups()
    if kind == "MessageDialog":
        return "message dialogs"
    if kind == "FontChooserDialog":
        return "font chooser"
    title = TAG_RE.sub("", title or "")
    if not title or "/" in title or title.endswith(".po - Virtaal") or title == "Virtaal":
        return "main window" if kind == "Window" else None
    return "%s dialog" % title


def harvested(paths):
    """{domain: {original: set(places)}} from resolve_sources.py outputs."""
    found = {domain: {} for domain in DOMAINS}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        for domain in DOMAINS:
            for entry in result.get(domain, []):
                within = set(entry["within"])
                if within and within <= EXCLUDED_WITHIN:
                    continue
                places = found[domain].setdefault(entry["original"], set())
                for window in entry["windows"]:
                    for kind in within or {""}:
                        place = _place(kind, window)
                        if place:
                            places.add(place)
    return found


def write_template(domain, originals):
    """Rewrite domain's template, keeping its header and developer
    comments."""
    path = os.path.join(LITE_DIR, domain, domain + ".pot")
    store = pypo.pofile()
    old_notes = {}
    if os.path.exists(path):
        old = factory.getobject(path)
        old_notes = {(unit.getcontext() or "", str(unit.source)):
                     "\n".join(line for line in unit.getnotes("developer").splitlines()
                               if not line.startswith("Seen in: "))
                     for unit in old.units if not unit.isheader()}
        store.units = [old.header()] if old.header() else []
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        store.init_headers(charset="UTF-8", encoding="8bit", project_id_version="%s lite" % domain)
    store.updateheader(pot_creation_date=time.strftime("%Y-%m-%d %H:%M%z"))
    if store.units:
        # pot2po copies the template's Language over each merged .po's own.
        store.units[0].target = "".join(
            line for line in store.units[0].target.splitlines(True) if not line.startswith("Language:"))
    for original in sorted(originals, key=lambda o: (o.rpartition("\x04")[2].lower(), o)):
        context, _, msgid = original.rpartition("\x04")
        forms = msgid.split("\0")
        unit = store.addsourceunit(multistring(forms) if len(forms) > 1 else forms[0])
        if context:
            unit.setcontext(context)
        note = old_notes.get((context, forms[0]))
        if note:
            unit.addnote(note, origin="developer")
        if originals[original]:
            unit.addnote("Seen in: " + "; ".join(sorted(originals[original])), origin="developer")
    with open(path, "wb") as f:
        store.serialize(f)
    return path


def merge(domain, template):
    for po in sorted(glob.glob(os.path.join(LITE_DIR, domain, "*.po"))):
        merged = po + ".new"
        subprocess.run([sys.executable, "-m", "translate.convert.pot2po", "--progress=none", "--nofuzzymatching",
                        "-t", po, template, merged], check=True)
        os.replace(merged, po)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("resolved", nargs="+", help="resolve_sources.py outputs, e.g. one per platform")
    parser.add_argument("--merge", action="store_true", help="also update each lite .po to its new template")
    args = parser.parse_args()
    found = harvested(args.resolved)
    for domain in DOMAINS:
        originals = found[domain]
        for original in KEEP[domain]:
            originals.setdefault(original, set())
        template = write_template(domain, originals)
        print("Wrote %d messages to %s" % (len(originals), template))
        if args.merge:
            merge(domain, template)


if __name__ == "__main__":
    main()
