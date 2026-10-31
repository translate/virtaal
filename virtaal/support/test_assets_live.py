#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Downloads every spelling dictionary, thesaurus and autocorrect list in
the published asset manifest the way Virtaal does, and checks Virtaal
can use each one (#4657). Run monthly and before a release by
live-assets.yml; skipped unless VIRTAAL_LIVE_ASSETS=1."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml
from gi.repository import GLib

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_ASSETS') != '1',
    reason="set VIRTAAL_LIVE_ASSETS=1 to download every asset")

PARALLEL = 6
PER_DOWNLOAD_SECONDS = 300


@pytest.fixture(scope='module')
def manifest(tmp_path_factory):
    from virtaal.support.asset_manifest import AssetManifest

    config_dir = tmp_path_factory.mktemp('config')
    fetched = []
    loop = GLib.MainLoop()
    AssetManifest(config_dir=str(config_dir), schedule_after_idle_lull=lambda cb: cb()).ensure_fresh(
        on_done=lambda: (fetched.append(True), loop.quit()))
    GLib.timeout_add_seconds(60, loop.quit)
    loop.run()
    cache = config_dir / 'asset-manifest.yaml'
    assert fetched and cache.exists(), 'the published manifest could not be fetched'
    data = yaml.safe_load(cache.read_text(encoding='utf-8'))
    assert {'dictionary', 'thesaurus', 'autocorrect'} <= set(data)
    return data


def _download_all(jobs):
    """jobs: [(key, start(on_done))]. Runs PARALLEL at a time; returns
    {key: True/False/None}, None meaning no answer in time (a failed
    connection never calls back)."""
    queue = list(jobs)
    results = {}
    active = [0]
    loop = GLib.MainLoop()

    def start_next():
        while queue and active[0] < PARALLEL:
            key, start = queue.pop(0)
            active[0] += 1
            state = {'done': False}

            def finish(ok, key=key, state=state):
                if not state['done']:
                    state['done'] = True
                    results[key] = ok
                    active[0] -= 1
                    if not queue and not active[0]:
                        loop.quit()
                    else:
                        start_next()
                return False

            GLib.timeout_add_seconds(PER_DOWNLOAD_SECONDS, finish, None)
            start(finish)

    start_next()
    if active[0]:
        loop.run()
    return results


def _groups(entries):
    """Locales sharing a folder and files download once."""
    groups = {}
    for locale, entry in sorted(entries.items()):
        key = (entry['folder'], tuple(f['name'] for f in entry['files']))
        groups.setdefault(key, []).append(locale)
    return groups


def _report(failures):
    return '\n'.join('%s: %s' % item for item in sorted(failures.items()))


# The spellchecker plugin's lookup: the locale itself, else the first
# installed language that starts with "<locale>_".
_SPELL_CHECK = r'''
import json, sys
import enchant
results = {}
for locale in json.loads(sys.argv[1]):
    code = locale if enchant.dict_exists(locale) else next(
        (c for c in enchant.list_languages() if c.startswith(locale + '_')), None)
    if code is None:
        results[locale] = 'enchant finds no dictionary for it'
        continue
    try:
        d = enchant.Dict(code)
        d.check('a')
        d.suggest('a')
    except Exception as e:
        results[locale] = 'enchant could not use %s: %s' % (code, e)
print(json.dumps(results))
'''


@pytest.mark.timeout(3600)
def test_every_spelling_dictionary(manifest, tmp_path):
    from virtaal.support.dictionary_downloader import DictionaryDownloader

    groups = _groups(manifest['dictionary'])
    jobs = []
    for i, ((folder, files), locales) in enumerate(groups.items()):
        target = tmp_path / str(i) / 'enchant' / 'hunspell'
        jobs.append(((folder, files), lambda done, l=locales[0], f=folder, fs=files, t=target:
                     DictionaryDownloader(l, on_done=done, target_dir=str(t)).start_with_known_files(f, list(fs))))
    downloaded = _download_all(jobs)

    failures = {}
    for i, (key, locales) in enumerate(groups.items()):
        if downloaded.get(key) is not True:
            for locale in locales:
                failures[locale] = 'download %s' % ('timed out' if downloaded.get(key) is None else 'failed')
            continue
        env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path / str(i)))
        run = subprocess.run([sys.executable, '-c', _SPELL_CHECK, json.dumps(locales)],
                             env=env, capture_output=True, text=True, timeout=300)
        if run.returncode:
            for locale in locales:
                failures[locale] = 'check crashed: %s' % run.stderr.strip().splitlines()[-1:]
            continue
        failures.update(json.loads(run.stdout))
    assert not failures, '%d of %d dictionaries:\n%s' % (
        len(failures), len(manifest['dictionary']), _report(failures))


@pytest.mark.timeout(3600)
def test_every_thesaurus(manifest, tmp_path):
    from virtaal.support.mythes import parse_thesaurus
    from virtaal.support.thesaurus_downloader import ThesaurusDownloader

    groups = _groups(manifest['thesaurus'])
    targets = {key: tmp_path / str(i) for i, key in enumerate(groups)}
    jobs = [(key, lambda done, l=locales[0], key=key: ThesaurusDownloader(
                 l, on_done=done, target_dir=str(targets[key])).start_with_known_files(key[0], list(key[1])))
            for key, locales in groups.items()]
    downloaded = _download_all(jobs)

    failures = {}
    for key, locales in groups.items():
        problem = None
        if downloaded.get(key) is not True:
            problem = 'download %s' % ('timed out' if downloaded.get(key) is None else 'failed')
        else:
            dat = [p for p in targets[key].iterdir() if p.suffix == '.dat']
            try:
                if not dat or not parse_thesaurus(dat[0].read_bytes()):
                    problem = 'no entries in %s' % (dat[0].name if dat else 'no .dat file')
            except Exception as e:
                problem = 'could not parse %s: %s' % (dat[0].name, e)
        if problem:
            failures.update(dict.fromkeys(locales, problem))
    assert not failures, '%d of %d thesauruses:\n%s' % (
        len(failures), len(manifest['thesaurus']), _report(failures))


@pytest.mark.timeout(3600)
def test_every_autocorrect_list(manifest, tmp_path):
    from virtaal.plugins.autocorrector import AutoCorrector
    from virtaal.support.autocorrect_downloader import AutocorrectDownloader

    entries = manifest['autocorrect']
    jobs = [(locale, lambda done, l=locale, e=entry: AutocorrectDownloader(
                 l, on_done=done, target_dir=str(tmp_path / l)).start_with_known_files(
                 e['folder'], [f['name'] for f in e['files']]))
            for locale, entry in sorted(entries.items())]
    downloaded = _download_all(jobs)

    corrector = AutoCorrector(SimpleNamespace(), acorpath=str(tmp_path))
    failures = {}
    for locale in entries:
        if downloaded.get(locale) is not True:
            failures[locale] = 'download %s' % ('timed out' if downloaded.get(locale) is None else 'failed')
            continue
        corrector.load_dictionary(locale, force=True)
        if corrector.unreadable or not corrector.correctiondict:
            failures[locale] = 'unreadable' if corrector.unreadable else 'no corrections loaded'
    assert not failures, '%d of %d autocorrect lists:\n%s' % (
        len(failures), len(entries), _report(failures))
