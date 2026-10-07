#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Reports, for each language Virtaal ships (po/LINGUAS, English
variants aside) and each library with a lite template, the template
messages that would still show in English: neither the library's own
catalog on this build host nor a shipped lite catalog translates them.

Upstream is what this host's library install holds - the catalogs a
frozen build here bundles. A language in po/LINGUAS-lite gets its lite
catalog merged into upstream's exact-language catalog, as setup.py
does; any other language gets upstream as gettext finds it at runtime
(pt_BR falling back to pt). A library this host doesn't have (gtkspell
or gtk-mac-integration on some platforms) is skipped: it isn't shipped.

Prints a Markdown report, also appended to $GITHUB_STEP_SUMMARY when
set, and one aggregate ::warning:: under GitHub Actions when anything
is missing. Never fails: missing translations are for translators to
fill, not a build error. To fill a gap, translate
po/lite/<domain>/<lang>.po (see po/README).
"""

import argparse
import gettext
import importlib.util
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PO_DIR = os.path.join(REPO_ROOT, "po")
LITE_DIR = os.path.join(PO_DIR, "lite")


def _lite_module():
    # From its file, as setup.py loads it: no virtaal package import.
    spec = importlib.util.spec_from_file_location(
        "lite", os.path.join(REPO_ROOT, "virtaal", "support", "libi18n", "lite.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lines(path):
    with open(path, encoding="utf-8") as f:
        return [line.split("#")[0].strip() for line in f if line.split("#")[0].strip()]


def shipped_languages():
    return [lang for lang in _lines(os.path.join(PO_DIR, "LINGUAS")) if not lang.startswith("en_")]


def shipped_lite():
    """{domain: {lang, ...}} from po/LINGUAS-lite."""
    shipped = {}
    for entry in _lines(os.path.join(PO_DIR, "LINGUAS-lite")):
        domain, lang = entry.split("/")
        shipped.setdefault(domain, set()).add(lang)
    return shipped


def template_keys(domain):
    """The lite template's messages, keyed as lite.read_mo() keys them."""
    from translate.storage import pypo
    with open(os.path.join(LITE_DIR, domain, domain + ".pot"), "rb") as f:
        units = pypo.pofile(f).units
    keys = []
    for unit in units:
        if unit.isheader():
            continue
        prefix = unit.getcontext() + "\x04" if unit.getcontext() else ""
        source = "\0".join(unit.source.strings) if unit.hasplural() else str(unit.source)
        keys.append(prefix + source)
    return keys


def translations(lite, domain, lang, upstream_dir, with_lite):
    """{original: translation} the shipped catalog for lang gives."""
    if with_lite:
        upstream = os.path.join(upstream_dir, lang, "LC_MESSAGES", domain + ".mo")
        lite_po = os.path.join(LITE_DIR, domain, lang + ".po")
        messages = lite.read_lite_po(lite_po) if os.path.isfile(lite_po) else {}
    else:
        upstream = gettext.find(domain, upstream_dir, [lang])
        messages = {}
    if upstream and os.path.isfile(upstream):
        messages.update({k: v for k, v in lite.read_mo(upstream).items() if v})
    return messages


def missing(lite=None):
    """{domain: {lang: [msgid, ...]}} of template messages that ship
        untranslated, and the domains skipped as not on this host."""
    lite = lite or _lite_module()
    languages, lite_shipped = shipped_languages(), shipped_lite()
    report, skipped = {}, []
    for domain, namespace in sorted(lite.LIBRARY_NAMESPACES.items()):
        upstream_dir = lite.library_locale_dir(namespace)
        if upstream_dir is None or not os.path.isfile(os.path.join(LITE_DIR, domain, domain + ".pot")):
            skipped.append(domain)
            continue
        keys = template_keys(domain)
        report[domain] = {}
        for lang in languages:
            have = translations(lite, domain, lang, upstream_dir, lang in lite_shipped.get(domain, ()))
            gaps = [key for key in keys if not have.get(key)]
            if gaps:
                report[domain][lang] = gaps
    return report, skipped


def _shown(key):
    context, _, msgid = key.rpartition("\x04")
    text = msgid.split("\0")[0].replace("\n", "\\n")
    return "%s (%s)" % (text, context) if context else text


LABELS = {"gtk30": "GTK", "glib20": "GLib", "gtkspell3": "gtkspell", "gtk-mac-integration": "macOS app menu"}


def _named(langs):
    """"nso (25 strings), af and ja (6), ...": most gaps first, languages
        with the same count named together, the unit only on the first."""
    groups = []
    for lang, count in sorted(langs.items(), key=lambda item: (-len(item[1]), item[0])):
        if groups and groups[-1][1] == len(count):
            groups[-1][0].append(lang)
        else:
            groups.append(([lang], len(count)))
    parts = []
    for names, count in groups:
        named = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        unit = "%d string%s" % (count, "" if count == 1 else "s") if not parts else str(count)
        parts.append("%s (%s)" % (named, unit))
    return ", ".join(parts)


def markdown(report, skipped, host):
    """A one-row-per-library summary, every gap in a collapsible section."""
    lines = ["## Lite coverage - %s" % host, "",
             "Library strings each shipped language would still show in English: neither the library's"
             " catalog on this build host nor a shipped lite catalog translates them.", "",
             "| Library | Languages with gaps |", "|---|---|"]
    for domain, langs in sorted(report.items(), key=lambda item: list(LABELS).index(item[0])):
        label = "%s (%d strings)" % (LABELS.get(domain, domain), len(template_keys(domain)))
        lines.append("| %s | %s |" % (label, _named(langs) if langs else "none"))
    for domain in skipped:
        lines.append("| %s | not on this build host, so not shipped |" % LABELS.get(domain, domain))
    lines += ["", "<details><summary>Every gap, by language</summary>", "",
              "To fill one, translate `po/lite/<domain>/<lang>.po` (see po/README.md).", ""]
    for domain, langs in sorted(report.items(), key=lambda item: list(LABELS).index(item[0])):
        if not langs:
            continue
        lines += ["**%s** (`%s`)" % (LABELS.get(domain, domain), domain), "",
                  "| Language | Missing | Messages |", "|---|---|---|"]
        for lang, gaps in sorted(langs.items()):
            lines.append("| %s | %d | %s |" % (lang, len(gaps), ", ".join(
                "`%s`" % _shown(key).replace("|", "\\|") for key in gaps)))
        lines.append("")
    lines += ["</details>", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default={"Darwin": "macOS"}.get(platform.system(), platform.system()),
                        help='this build host, as the report names it (e.g. "macOS (Homebrew)")')
    args = parser.parse_args(argv)
    report, skipped = missing()
    text = markdown(report, skipped, args.host)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    languages = {lang for langs in report.values() for lang in langs}
    messages = sum(len(gaps) for langs in report.values() for gaps in langs.values())
    if languages and os.environ.get("GITHUB_ACTIONS"):
        # One aggregate annotation: GitHub caps them at ~10 per step.
        print("::warning title=Lite coverage gaps (%s)::%d shipped language(s) show %d library message(s)"
              " in English - see the job summary's Lite coverage - %s report."
              % (args.host, len(languages), messages, args.host))
    return 0


if __name__ == "__main__":
    sys.exit(main())
