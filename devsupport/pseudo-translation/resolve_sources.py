#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Maps the tagged strings harvest_sources.py recorded back to the
msgids they came from, using the pseudo-source catalogs
generate_pseudo_translation.py wrote.

A tag (vt:, gtk:, glib:, spell:, mac:, iso:, or gtk!: and so on for a
message its lite template lacks) marks where a translated message starts; the
msgid of that domain with the most literal text matching there - printf
conversions as wildcards, ending at a word boundary - is the one shown. Text with a
tag but no matching msgid is reported as unresolved.

Writes JSON: {domain: [{"original", "screens", "within", "shown"}, ...],
"unresolved": [...]}, with "original" as stored in a .mo file (msgctxt
before \\x04, msgid_plural after \\0). Strings only ever seen inside
GTK's own file chooser are flagged by "within" ("FileChooser"): Windows and macOS show
the OS's file dialog instead. "shown" is false for a message only ever
seen in a hidden widget.
"""

import argparse
import collections
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# iso: covers both language and country names.
DOMAINS = {"virtaal": "vt:", "gtk30": "gtk:", "glib20": "glib:", "gtkspell3": "spell:", "gtk-mac-integration": "mac:", "iso639-3": "iso:", "iso3166-1": "iso:"}
TAG_RE = re.compile(r"(?:vt|gtk|glib|iso|spell|mac)!?:")
# The harvest records labels without their Pango markup.
MARKUP_RE = re.compile(r"<[^>]+>")
PRINTF_RE = re.compile(r"%(?:\d+\$)?[-+ #0']*\d*(?:\.\d+)?[hlLqjzt]*[diouxXeEfFgGcspa]|%%")


def _generator():
    spec = importlib.util.spec_from_file_location(
        "generate_pseudo_translation", os.path.join(HERE, "generate_pseudo_translation.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def msgid_pattern(form):
    """A regex matching a message as shown: printf conversions match
    anything, %% a literal %."""
    parts = []
    position = 0
    for match in PRINTF_RE.finditer(form):
        parts.append(re.escape(form[position:match.start()]))
        parts.append("%" if match.group() == "%%" else ".*?")
        position = match.end()
    parts.append(re.escape(form[position:]))
    # Must end at the end of the text or before a non-word character.
    return re.compile("".join(parts) + r"(?=$|\W)", re.DOTALL)


def load_catalogs(locale_dir):
    """{domain: [(original, form, pattern), ...]} from the pseudo-source
    catalogs, one entry per singular and plural form."""
    read_mo_originals = _generator().read_mo_originals
    catalogs = {}
    for domain in DOMAINS:
        path = os.path.join(locale_dir, "pseudo-source", "LC_MESSAGES", domain + ".mo")
        if not os.path.isfile(path):
            continue
        entries = []
        for original in read_mo_originals(path):
            msgid = original.rpartition("\x04")[2]
            for form in msgid.split("\0"):
                form = MARKUP_RE.sub("", form)
                if form.strip():
                    entries.append((original, form, msgid_pattern(form)))
        catalogs[domain] = entries
    return catalogs


def resolve_text(text, catalogs):
    """[(domain, original) ...] for each tag in text - every original
    whose form matches equally well, since the same text can come from
    several msgctxts - or (domain, None) for a tag nothing matches."""
    found = []
    for tag_match in TAG_RE.finditer(text):
        tag = tag_match.group().replace("!", "")
        domains = [d for d, t in DOMAINS.items() if t == tag and d in catalogs]
        if not domains:
            continue
        start = tag_match.end()
        best, best_length = [], -1
        for domain in domains:
            for original, form, pattern in catalogs[domain]:
                if pattern.match(text, start):
                    # Ranked by literal text, not placeholders: "kB" over
                    # "%.1f", which matches anything.
                    length = len(PRINTF_RE.sub("", form))
                    if length > best_length:
                        best, best_length = [], length
                    if length == best_length:
                        best.append((domain, original))
        found.extend(best or [(domains[0], None)])
    return found


def resolve(harvest, catalogs):
    seen = collections.defaultdict(lambda: {"screens": set(), "within": set(), "windows": set(), "shown": False})
    unresolved = set()
    for record in harvest["strings"]:
        for domain, original in resolve_text(record["text"], catalogs):
            if original is None:
                unresolved.add(record["text"])
                continue
            entry = seen[(domain, original)]
            entry["screens"].add(record["screen"].split(" > ")[0])
            entry["within"].add(record.get("within") or "")
            entry["windows"].add(record.get("window") or "")
            entry["shown"] = entry["shown"] or record.get("shown", True)
    result = collections.defaultdict(list)
    for (domain, original), entry in sorted(seen.items()):
        result[domain].append({"original": original, "screens": sorted(entry["screens"]),
                               "within": sorted(entry["within"]), "windows": sorted(entry["windows"]),
                               "shown": entry["shown"]})
    result["unresolved"] = sorted(unresolved)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("harvest", help="harvest_sources.py's JSON output")
    parser.add_argument("output", help="JSON file to write")
    parser.add_argument("--localedir", default=os.path.join(sys.prefix, "share", "locale"),
                        help="Where the pseudo-source catalogs are (default: sys.prefix/share/locale)")
    args = parser.parse_args()
    with open(args.harvest, encoding="utf-8") as f:
        harvest = json.load(f)
    result = resolve(harvest, load_catalogs(args.localedir))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    for domain, entries in result.items():
        print("%s: %d" % (domain, len(entries)))


if __name__ == "__main__":
    main()
