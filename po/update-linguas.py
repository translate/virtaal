#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Applies the release threshold to po/LINGUAS, the translations
    setup.py builds and ships: a po/<lang>.po ships when it translates
    at least THRESHOLD percent of the current po/virtaal.pot's messages
    (fuzzy ones don't count). English variants (en_*) always ship - they
    only translate what differs from the source. EXCLUDED languages never
    ship, whatever their coverage.

    Until ENFORCE_REMOVALS is set (when cutting the final release), a
    language already in po/LINGUAS stays there below the threshold:
    translators get the string freeze's release candidates (rc1, then a
    translations-only rc2) to catch up on new strings before they're
    dropped.

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
TEMPLATE = PO_DIR / 'virtaal.pot'
THRESHOLD = 50
ENFORCE_REMOVALS = False
EXCLUDED = {
    'ach': 'disabled for an abundance of serious issues (d46e9821, 2012)',
}


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


def qualifies(lang, percent):
    if lang in EXCLUDED:
        return False
    return lang.startswith('en_') or percent >= THRESHOLD


def expected(current):
    """{lang: percent} of every translation, and the po/LINGUAS the rule
        gives starting from current."""
    total = sum(_statistics(TEMPLATE.read_bytes()).values())
    percents = {po.stem: coverage(po, total) for po in sorted(PO_DIR.glob('*.po'))}
    ships = {lang for lang, percent in percents.items() if qualifies(lang, percent)}
    if not ENFORCE_REMOVALS:
        ships |= {lang for lang in current if lang in percents and lang not in EXCLUDED}
    return percents, sorted(ships)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help="report differences, don't write")
    args = parser.parse_args()

    current = LINGUAS.read_text(encoding='utf-8').split()
    percents, ships = expected(current)
    for lang in sorted(set(ships) - set(current)):
        print('add %s (%d%%)' % (lang, percents[lang]))
    for lang in sorted(set(current) - set(ships)):
        reason = EXCLUDED.get(lang) or ('%d%%' % percents[lang] if lang in percents else 'no po file')
        print('remove %s (%s)' % (lang, reason))
    if not ENFORCE_REMOVALS:
        for lang in sorted(lang for lang in ships if not qualifies(lang, percents[lang])):
            print('below %d%%, dropped once ENFORCE_REMOVALS is set: %s (%d%%)'
                  % (THRESHOLD, lang, percents[lang]))

    if ships == current:
        return 0
    if args.check:
        print('po/LINGUAS is out of date: run po/update-linguas.py')
        return 1
    LINGUAS.write_text(''.join(lang + '\n' for lang in ships), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
