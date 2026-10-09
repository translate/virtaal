#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Level packs: a translation cut down to what users see most (see
    po/virtaal.priorities.yaml), for a translator to finish first.

    po/level-pack.py LANG [LANG ...]   (or --all)

    writes OUT/<lang>.zip (--out, default dist/level-packs): <lang>-level1.po,
    po/<lang>.po merged into level 1 of virtaal.pot; <lang>-level2.po,
    levels 1 and 2; and the priority file they name in their header.
    With --libraries, also <domain>-<lang>-level1.po (and -level2) for
    each library (GTK, GLib, ...) and the language names: only the
    messages neither the library's catalog on this host nor the lite
    catalog in po/lite translates. Run that where Virtaal runs.

    po/level-pack.py --merge LANG FILE.po

    merges a pack a translator sends back into po/<lang>.po, or a
    <domain>-<lang>-level*.po one into po/lite/<domain>/<lang>.po: its
    translations replace the ones there, or are added if po/<lang>.po
    doesn't have the message yet; an untranslated or fuzzy one in it
    leaves the one there alone. Nothing else in the catalog changes."""

import argparse
import importlib.util
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent
TEMPLATE = PO_DIR / 'virtaal.pot'
PRIORITIES = PO_DIR / 'virtaal.priorities.yaml'
LINGUAS = PO_DIR / 'LINGUAS'
LITE_DIR = PO_DIR / 'lite'
LANGUAGE_NAMES = ('iso639-3', 'iso639-5')
OUT = PO_DIR.parent / 'dist' / 'level-packs'
# Each pack level: the priority levels it holds.
PACK_LEVELS = {1: ('1', '1~'), 2: ('1', '1~', '2')}


def _run(*command):
    result = subprocess.run([str(part) for part in command], capture_output=True)
    if result.returncode:
        sys.exit('%s failed: %s' % (command[0], result.stderr.decode(errors='replace')))
    return result


def level_keys(level, domain='virtaal'):
    """domain's messages, as msgctxt\\x04msgid, at pack level."""
    import yaml
    with open(PRIORITIES, encoding='utf-8') as f:
        priorities = yaml.safe_load(f)['domains'].get(domain, {})
    return {key for priority in PACK_LEVELS[level] for key in priorities.get(priority, [])}


def library_gaps():
    """{lang: {domain: {key, ...}}}: the library messages and language
        names each shipped language shows in English on this host (see
        devsupport/pseudo-translation/report_lite_coverage.py)."""
    path = PO_DIR.parent / 'devsupport' / 'pseudo-translation' / 'report_lite_coverage.py'
    spec = importlib.util.spec_from_file_location('report_lite_coverage', path)
    coverage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage)
    lite = coverage._lite_module()
    report, _skipped = coverage.missing(lite)
    gaps = {}
    for domain, langs in report.items():
        for lang, keys in langs.items():
            gaps.setdefault(lang, {})[domain] = {key.split('\0')[0] for key in keys}
    for domain in LANGUAGE_NAMES:
        names = {key for level in PACK_LEVELS for key in level_keys(level, domain)}
        for lang in coverage.shipped_languages():
            missing = {name for name in names if not coverage._name_translated(lite, lang, name, domain)}
            if missing:
                gaps.setdefault(lang, {})[domain] = missing
    return gaps


def _new_catalog(domain, lang, path):
    """A new, empty lite catalog for lang: from the domain's template, or
        just a header for language names, which have none."""
    template = LITE_DIR / domain / (domain + '.pot')
    if template.is_file():
        _run('msginit', '--no-translator', '-l', lang, '-i', template, '-o', path)
    else:
        path.write_text('msgid ""\nmsgstr ""\n"Language: %s\\n"\n"MIME-Version: 1.0\\n"\n'
                        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
                        '"Content-Transfer-Encoding: 8bit\\n"\n' % lang, encoding='utf-8', newline='\n')


def write_library_pack(domain, lang, keys, path):
    """path: the lite catalog for lang cut down to keys."""
    from translate.storage import po
    with tempfile.TemporaryDirectory() as tmp:
        catalog = LITE_DIR / domain / (lang + '.po')
        if not catalog.is_file():
            catalog = Path(tmp) / 'new.po'
            _new_catalog(domain, lang, catalog)
        store = po.pofile.parsefile(str(catalog))
    present = {unit.getid() for unit in store.units if not unit.isheader() and not unit.isobsolete()}
    store.units = [unit for unit in store.units
                   if unit.isheader() or (unit.getid() in keys and not unit.isobsolete())]
    for key in sorted(keys - present):
        context, _sep, msgid = key.rpartition('\x04')
        unit = store.addsourceunit(msgid)
        if context:
            unit.setcontext(context)
    store.updateheader(add=True, X_Priority_File=PRIORITIES.name)
    store.savefile(str(path))


def write_template(keys, path):
    """virtaal.pot with only the messages in keys."""
    from translate.storage import po
    template = po.pofile.parsefile(str(TEMPLATE))
    template.units = [unit for unit in template.units if unit.isheader() or unit.getid() in keys]
    template.savefile(str(path))


def _set_header_field(path, name, value):
    from translate.storage import po
    store = po.pofile.parsefile(str(path))
    store.updateheader(add=True, **{name.replace('-', '_'): value})
    store.savefile(str(path))


def pack(lang, out_dir, gaps=None):
    """Writes out_dir/<lang>.zip, and returns its path. gaps:
        library_gaps()[lang], for the library packs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / (lang + '.zip')
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        for level in PACK_LEVELS:
            template = Path(tmp) / ('level%d.pot' % level)
            write_template(level_keys(level), template)
            merged = Path(tmp) / 'merged.po'
            name = '%s-level%d.po' % (lang, level)
            _run('msgmerge', '--quiet', '--no-fuzzy-matching', PO_DIR / (lang + '.po'), template, '-o', merged)
            _run('msgattrib', '--no-obsolete', merged, '-o', Path(tmp) / name)
            _set_header_field(Path(tmp) / name, 'X-Priority-File', PRIORITIES.name)
            zf.write(Path(tmp) / name, name)
            for domain, keys in sorted((gaps or {}).items()):
                keys = keys & level_keys(level, domain)
                if keys:
                    name = '%s-%s-level%d.po' % (domain, lang, level)
                    write_library_pack(domain, lang, keys, Path(tmp) / name)
                    zf.write(Path(tmp) / name, name)
        zf.write(PRIORITIES, PRIORITIES.name)
    return archive


def merge_target(lang, returned):
    """The catalog a returned pack file goes back into, and its library
        domain: po/lite/<domain>/<lang>.po for <domain>-<lang>-level*.po,
        else po/<lang>.po."""
    match = re.match(r'(.+)-%s-level\d+\.po$' % re.escape(lang), returned.name)
    if match and ((LITE_DIR / match.group(1)).is_dir() or match.group(1) in LANGUAGE_NAMES):
        return LITE_DIR / match.group(1) / (lang + '.po'), match.group(1)
    return PO_DIR / (lang + '.po'), None


def merge(lang, returned):
    """Merges returned (a pack .po) into its catalog, changing only the
        messages it translates: one already there gets the new
        translation, one not there yet is added at the end."""
    from translate.storage import po
    target_path, domain = merge_target(lang, returned)
    if domain and not target_path.is_file():
        target_path.parent.mkdir(exist_ok=True)
        _new_catalog(domain, lang, target_path)
    with tempfile.TemporaryDirectory() as tmp:
        # A real file: Windows' msgfmt takes no null device.
        _run('msgfmt', '-c', '-o', Path(tmp) / 'check.mo', returned)
    target = po.pofile.parsefile(str(target_path))
    units = {unit.getid(): unit for unit in target.units if not unit.isheader()}
    for new in po.pofile.parsefile(str(returned)).units:
        if new.isheader() or not new.istranslated():
            continue
        unit = units.get(new.getid())
        if unit is not None and unit.isobsolete():
            target.units.remove(unit)
            unit = None
        if unit is None:
            target.addunit(new)
        elif unit.target != new.target or unit.isfuzzy():
            unit.target = new.target
            unit.markfuzzy(False)
    target.savefile(str(target_path))
    with tempfile.TemporaryDirectory() as tmp:
        _run('msgfmt', '-c', '-o', Path(tmp) / 'check.mo', target_path)


def _shipped():
    return [lang for lang in LINGUAS.read_text(encoding='utf-8').split() if not lang.startswith('en_')]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('languages', nargs='*', metavar='LANG')
    parser.add_argument('--all', action='store_true', help='every shipped language (po/LINGUAS), English variants aside')
    parser.add_argument('--out', type=Path, default=OUT, help='where to write the packs (default dist/level-packs)')
    parser.add_argument('--libraries', action='store_true',
                        help="add the library messages and language names this host shows in English")
    parser.add_argument('--merge', nargs=2, metavar=('LANG', 'FILE'), help='merge a returned pack into po/LANG.po')
    args = parser.parse_args()
    if args.merge:
        merge(args.merge[0], Path(args.merge[1]))
        return 0
    languages = _shipped() if args.all else args.languages
    if not languages:
        parser.error('name languages, or use --all')
    gaps = library_gaps() if args.libraries else {}
    for lang in languages:
        print(pack(lang, args.out, gaps.get(lang)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
