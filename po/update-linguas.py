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
# --report's bands, in strings: could make it, could slip.
REACHABLE = 60
AT_RISK = 20


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


def translated(po_path):
    """How many of the template's messages po_path translates, as
        msgmerge sees it."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = os.path.join(tmp, 'merged.po')
        result = subprocess.run(['msgmerge', '--quiet', '--no-fuzzy-matching', '-o', merged, str(po_path), str(TEMPLATE)],
                                capture_output=True)
        if result.returncode:
            sys.exit('msgmerge failed: %s' % result.stderr.decode(errors='replace'))
        with open(merged, 'rb') as f:
            merged = f.read()
    return _statistics(merged).get('translated', 0)


def standing(langs):
    """{lang: strings over (+) or under (-) THRESHOLD} of langs, English
        variants aside, and the template's message count."""
    total = sum(_statistics(TEMPLATE.read_bytes()).values())
    needed = -(-THRESHOLD * total // 100)  # ceil: the fewest that reach it
    return {lang: translated(PO_DIR / (lang + '.po')) - needed
            for lang in langs if not lang.startswith('en_')}, total


def below_threshold(langs):
    """{lang: percent} of langs, English variants aside, under THRESHOLD."""
    margins, total = standing(langs)
    needed = -(-THRESHOLD * total // 100)
    return {lang: 100 * (margin + needed) / total for lang, margin in margins.items() if margin < 0}


def _named(langs, counts, unit):
    """"lg (7 strings needed), cgg (11), bg and vi (23)": langs in order,
        those sharing a count named together, unit only on the first."""
    groups = []
    for lang in langs:
        if groups and groups[-1][1] == counts[lang]:
            groups[-1][0].append(lang)
        else:
            groups.append(([lang], counts[lang]))
    parts = []
    for names, count in groups:
        named = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
        first = unit % count if count != 1 else unit.replace('strings', 'string') % count
        parts.append('%s (%s)' % (named, first if not parts else count))
    return ', '.join(parts) or '-'


def report(langs):
    """Markdown: who could make THRESHOLD and who could slip under it,
        with every translation's numbers in a collapsible section."""
    margins, total = standing(langs)
    needed = -(-THRESHOLD * total // 100)
    shortfall = {lang: -margin for lang, margin in margins.items()}

    reach = sorted((lang for lang, m in margins.items() if -REACHABLE <= m < 0), key=lambda lang: -margins[lang])
    slip = sorted((lang for lang, m in margins.items() if 0 <= m < AT_RISK), key=lambda lang: margins[lang])
    far = sorted((lang for lang, m in margins.items() if m < -REACHABLE), key=lambda lang: -margins[lang])
    group = dict.fromkeys(reach, 'could make it')
    group.update(dict.fromkeys(slip, 'could slip'))
    group.update(dict.fromkeys(far, 'further off'))

    lines = ['## Release threshold', '',
             'A final release needs %d of %d strings (%d%%, `po/update-linguas.py --cut-off`).'
             % (needed, total, THRESHOLD), '',
             '| Group | Languages |', '|---|---|',
             '| Could make it | %s |' % _named(reach, shortfall, '%d strings needed'),
             '| Could slip | %s |' % _named(slip, margins, '%d to spare'),
             '| Further off | %s |' % _named(far, shortfall, 'needs %d'),
             '', '<details><summary>Every shipped translation</summary>', '',
             'Could make it: under the threshold by at most %d strings. Could slip: at most %d strings '
             'over it - new strings in virtaal.pot dilute coverage until the rc1 string freeze. '
             'Fuzzy translations don\'t count; English variants always ship.' % (REACHABLE, AT_RISK - 1), '',
             '| Language | Coverage | Over (+) / under (-) | Group |', '|---|---|---|---|']
    lines += ['| %s | %d%% | %+d | %s |' % (lang, 100 * (margins[lang] + needed) // total, margins[lang],
                                           group.get(lang, 'safe'))
              for lang in sorted(margins)]
    lines += ['', '</details>', '']
    return '\n'.join(lines)


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
    group.add_argument('--report', action='store_true',
                       help='where each shipped translation stands against the threshold (Markdown)')
    args = parser.parse_args()

    if args.report:
        skip = excluded()
        text = report([lang for lang in catalogs() if lang not in skip])
        print(text)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(text + '\n')
        return 0

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
