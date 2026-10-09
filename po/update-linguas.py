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

    --cut-off VERSION applies the release rule, when cutting a final
    release: a shipped translation needs all of level 1 in
    po/virtaal.priorities.yaml - every core message, and all but
    LEVEL_ONE_TOLERANCE of the rest (fuzzy ones don't count). Before
    FIFTY_PERCENT_UNTIL, translating THRESHOLD percent of
    po/virtaal.pot's messages also ships it. Any other is added to
    po/LINGUAS-excluded, with what it's missing as the reason. Level 1
    includes GTK's and the other libraries' messages, as this host's
    catalogs and the lite ones translate them, so run it where Virtaal
    runs. --report counts Virtaal's own messages only. English
    variants (en_*) are exempt - they only translate what differs from
    the source. Translators get the release candidates (rc1, then a
    translations-only rc2) to catch up first.

    With --check, changes nothing: prints how po/LINGUAS differs from the
    rule and exits 1 if it does. Uses gettext's own tools only, so the
    pre-commit job needs no Python packages."""

import argparse
import importlib.util
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent
LINGUAS = PO_DIR / 'LINGUAS'
EXCLUDED = PO_DIR / 'LINGUAS-excluded'
TEMPLATE = PO_DIR / 'virtaal.pot'
PRIORITIES = PO_DIR / 'virtaal.priorities.yaml'
LEVEL_ONE_TOLERANCE = 3
# THRESHOLD percent also ships a translation in releases before this.
FIFTY_PERCENT_UNTIL = (1, 1)
THRESHOLD = 50
# --report's band, in level-1 strings needed: could make it.
REACHABLE = 30


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


def _mo_keys(mo):
    """The messages a compiled catalog (bytes) has, as msgctxt\x04msgid
        without any plural."""
    order = '<' if struct.unpack('<I', mo[:4])[0] == 0x950412de else '>'
    _revision, count, originals = struct.unpack(order + 'III', mo[4:16])
    keys = set()
    for i in range(count):
        length, offset = struct.unpack(order + 'II', mo[originals + 8 * i:originals + 8 * i + 8])
        key = mo[offset:offset + length].decode('utf-8').split('\0')[0]
        if key:
            keys.add(key)
    return keys


def _compiled_keys(*commands):
    """The messages msgfmt keeps (translated, not fuzzy) of the catalog
        the commands make, each run as command + [output]."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'messages.po')
        for command in commands:
            result = subprocess.run(command + [path], capture_output=True)
            if result.returncode:
                sys.exit('%s failed: %s' % (command[0], result.stderr.decode(errors='replace')))
        mo = os.path.join(tmp, 'messages.mo')
        result = subprocess.run(['msgfmt', '-o', mo, path], capture_output=True)
        if result.returncode:
            sys.exit('msgfmt failed: %s' % result.stderr.decode(errors='replace'))
        with open(mo, 'rb') as f:
            return _mo_keys(f.read())


def template_keys():
    return _compiled_keys(['msgen', str(TEMPLATE), '-o'])


def translated_keys(po_path):
    return _compiled_keys(['msgmerge', '--quiet', '--no-fuzzy-matching', str(po_path), str(TEMPLATE), '-o'])


def level_one():
    """(core, rest): virtaal.pot's level-1 messages, as
        po/virtaal.priorities.yaml has them."""
    import yaml
    with open(PRIORITIES, encoding='utf-8') as f:
        levels = yaml.safe_load(f)['domains']['virtaal']
    current = template_keys()
    return set(levels.get('1', [])) & current, set(levels.get('1~', [])) & current


def library_gaps():
    """{lang: (core, rest)}: the level-1 messages of GTK and the other
        libraries, and language names, this host shows in English (see
        devsupport/pseudo-translation/report_lite_coverage.py)."""
    path = PO_DIR.parent / 'devsupport' / 'pseudo-translation' / 'report_lite_coverage.py'
    spec = importlib.util.spec_from_file_location('report_lite_coverage', path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.level_one_gaps()
    except ImportError as e:
        sys.exit("--cut-off counts the libraries' level-1 messages on this host, which needs Virtaal's own"
                 " environment: %s" % e)


def readiness(langs, libraries=None):
    """{lang: (core missing, rest missing, strings over (+) or under (-)
        THRESHOLD)} of langs, English variants aside. libraries:
        library_gaps(), added to Virtaal's own."""
    core, rest = level_one()
    margins, _total = standing(langs)
    result = {}
    for lang in margins:
        have = translated_keys(PO_DIR / (lang + '.po'))
        library_core, library_rest = (libraries or {}).get(lang, (0, 0))
        result[lang] = (len(core - have) + library_core, len(rest - have) + library_rest, margins[lang])
    return result


def _needed(core_missing, rest_missing):
    """The level-1 strings a translation still needs."""
    return core_missing + max(0, rest_missing - LEVEL_ONE_TOLERANCE)


def _version(version):
    match = re.match(r'(\d+)\.(\d+)', version)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def ships(state, version=None):
    """Which rule ships a translation with readiness() state: 'level 1',
        '50%' (before FIFTY_PERCENT_UNTIL), or None."""
    core_missing, rest_missing, margin = state
    if _needed(core_missing, rest_missing) == 0:
        return 'level 1'
    if margin >= 0 and (version is None or _version(version) < FIFTY_PERCENT_UNTIL):
        return '50%'
    return None


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
    """Markdown: who has level 1, who ships on 50% only, who could make
        level 1, with every translation's numbers in a collapsible
        section."""
    states = readiness(langs)
    core, rest = level_one()
    needed = {lang: _needed(c, r) for lang, (c, r, _m) in states.items()}
    ready = sorted(lang for lang in states if ships(states[lang]) == 'level 1')
    fifty = sorted((lang for lang in states if ships(states[lang]) == '50%'), key=lambda lang: needed[lang])
    reach = sorted((lang for lang in states if not ships(states[lang]) and needed[lang] <= REACHABLE),
                   key=lambda lang: needed[lang])
    far = sorted((lang for lang in states if not ships(states[lang]) and needed[lang] > REACHABLE),
                 key=lambda lang: needed[lang])
    group = dict.fromkeys(ready, 'level 1')
    group.update(dict.fromkeys(fifty, '50% only'))
    group.update(dict.fromkeys(reach, 'could make it'))
    group.update(dict.fromkeys(far, 'further off'))

    lines = ['## Release readiness', '',
             'A final release ships a translation with all of level 1: the %d core strings, and all but %d of'
             ' the other %d (`po/update-linguas.py --cut-off`). Until %d.%d.0, translating %d%% of all strings'
             ' also ships it. Counted here: Virtaal\'s own strings; GTK\'s are in each build\'s Lite coverage'
             ' report.' % (len(core), LEVEL_ONE_TOLERANCE, len(rest), *FIFTY_PERCENT_UNTIL, THRESHOLD), '',
             '| Group | Languages |', '|---|---|',
             '| Level 1 | %s |' % (', '.join(ready) or '-'),
             '| 50%% only, until %d.%d.0 | %s |' % (*FIFTY_PERCENT_UNTIL, _named(fifty, needed, '%d level-1 strings needed')),
             '| Could make level 1 | %s |' % _named(reach, needed, '%d strings needed'),
             '| Further off | %s |' % _named(far, needed, 'needs %d'),
             '', '<details><summary>Every shipped translation</summary>', '',
             'Strings needed counts core strings missing, and the rest missing beyond %d. Could make it: at'
             ' most %d needed. Fuzzy translations don\'t count; English variants always ship.'
             % (LEVEL_ONE_TOLERANCE, REACHABLE), '',
             '| Language | Core missing | Rest missing | Needed | %d%% over (+) / under (-) | Group |' % THRESHOLD,
             '|---|---|---|---|---|---|']
    lines += ['| %s | %d | %d | %d | %+d | %s |' % (lang, c, r, needed[lang], m, group[lang])
              for lang, (c, r, m) in sorted(states.items())]
    lines += ['', '</details>', '']
    return '\n'.join(lines)


def cut_off(version):
    """Excludes the shipped translations the release rule doesn't ship,
        from version on."""
    skip = excluded()
    states = readiness([lang for lang in catalogs() if lang not in skip], library_gaps())
    with open(EXCLUDED, 'a', encoding='utf-8') as f:
        for lang, state in sorted(states.items()):
            if ships(state, version):
                continue
            core_missing, rest_missing, _margin = state
            f.write('%s  # level 1 incomplete at %s (%d core, %d other strings missing)\n'
                    % (lang, version, core_missing, rest_missing))
            print('excluded %s (%d core, %d other strings missing)' % (lang, core_missing, rest_missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true', help="report differences, don't write")
    group.add_argument('--cut-off', metavar='VERSION', help="exclude translations the release rule doesn't ship")
    group.add_argument('--report', action='store_true',
                       help='where each shipped translation stands against the release rule (Markdown)')
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
