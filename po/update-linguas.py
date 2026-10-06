#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Keeps po/LINGUAS, the translations setup.py builds and ships, to
    every po/<lang>.po not in po/LINGUAS-excluded - so a translation is
    only ever left out on purpose, with a reason.

    --cut-off VERSION applies the release threshold, when cutting a final
    release: each shipped translation covering less than THRESHOLD
    percent of the current po/virtaal.pot's messages (fuzzy ones don't
    count) is added to po/LINGUAS-excluded, its coverage as the reason.
    English variants (en_*) are exempt - they only translate what
    differs from the source. Translators get the release candidates
    (rc1, then a translations-only rc2) to catch up first.

    With --check, changes nothing: prints how po/LINGUAS differs from the
    rule and exits 1 if it does. Uses gettext's own tools only, so the
    pre-commit job needs no Python packages."""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent
LINGUAS = PO_DIR / 'LINGUAS'
EXCLUDED = PO_DIR / 'LINGUAS-excluded'
TEMPLATE = PO_DIR / 'virtaal.pot'
THRESHOLD = 50


def excluded():
    """{lang: reason} from po/LINGUAS-excluded ("lang  # reason" lines)."""
    lines = EXCLUDED.read_text(encoding='utf-8').splitlines()
    return {line.partition('#')[0].strip(): line.partition('#')[2].strip()
            for line in lines if line.strip() and not line.startswith('#')}


def catalogs():
    return sorted(po.stem for po in PO_DIR.glob('*.po'))


def _statistics(po):
    """msgfmt --statistics' counts of po (bytes): {'translated': n, ...}."""
    # Real files rather than stdin and a null device: Windows' msgfmt
    # takes neither.
    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, 'messages.po')
        with open(source, 'wb') as f:
            f.write(po)
        result = subprocess.run(['msgfmt', '--statistics', '-o', os.path.join(tmp, 'messages.mo'), source],
                                capture_output=True)
    if result.returncode:
        sys.exit('msgfmt failed: %s' % result.stderr.decode(errors='replace'))
    return {kind.decode(): int(n)
            for n, kind in re.findall(rb'(\d+) (translated|fuzzy|untranslated)', result.stderr)}


def coverage(po_path, total):
    """Percentage of the template's messages po_path translates, as
        msgmerge sees it."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = os.path.join(tmp, 'merged.po')
        result = subprocess.run(['msgmerge', '--quiet', '--no-fuzzy-matching', '-o', merged, str(po_path), str(TEMPLATE)],
                                capture_output=True)
        if result.returncode:
            sys.exit('msgmerge failed: %s' % result.stderr.decode(errors='replace'))
        with open(merged, 'rb') as f:
            merged = f.read()
    return 100 * _statistics(merged).get('translated', 0) / total


def below_threshold(langs):
    """{lang: percent} of langs, English variants aside, under THRESHOLD."""
    total = sum(_statistics(TEMPLATE.read_bytes()).values())
    percents = {lang: coverage(PO_DIR / (lang + '.po'), total) for lang in langs if not lang.startswith('en_')}
    return {lang: percent for lang, percent in percents.items() if percent < THRESHOLD}


def cut_off(version):
    """Excludes the shipped translations below THRESHOLD, from version on."""
    skip = excluded()
    cut = below_threshold([lang for lang in catalogs() if lang not in skip])
    with open(EXCLUDED, 'a', encoding='utf-8') as f:
        for lang, percent in sorted(cut.items()):
            f.write('%s  # below %d%% at %s (%d%%)\n' % (lang, THRESHOLD, version, percent))
            print('excluded %s (%d%%)' % (lang, percent))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true', help="report differences, don't write")
    group.add_argument('--cut-off', metavar='VERSION', help='exclude translations below the threshold')
    args = parser.parse_args()

    if args.cut_off:
        cut_off(args.cut_off)

    skip = excluded()
    current = LINGUAS.read_text(encoding='utf-8').split()
    ships = [lang for lang in catalogs() if lang not in skip]
    for lang in sorted(set(ships) - set(current)):
        print('add %s' % lang)
    for lang in sorted(set(current) - set(ships)):
        print('remove %s (%s)' % (lang, skip.get(lang) or 'no po file'))

    if ships == current:
        return 0
    if args.check:
        print('po/LINGUAS is out of date: run po/update-linguas.py')
        return 1
    LINGUAS.write_text(''.join(lang + '\n' for lang in ships), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
