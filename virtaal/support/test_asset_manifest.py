#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for AssetManifest - a _FakeClient records .get() calls
instead of doing real network I/O, and schedule_after_idle_lull is
injected as a function that just calls back immediately, so no test
needs a real GLib main loop."""

from datetime import date, timedelta

import yaml

from virtaal.common import pan_app
from virtaal.support import asset_manifest as am

YAML_BYTES = yaml.safe_dump({
    'dictionary': {
        'de_DE': {'folder': 'de', 'files': [
            {'name': 'de_DE_frami.aff', 'sha': 'a1'},
            {'name': 'de_DE_frami.dic', 'sha': 'a2'},
        ]},
    },
}).encode('utf-8')


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, error_callback=None):
        self.calls.append((url, callback, error_callback))


def _make_manifest(tmp_path, client=None, lull_calls=None):
    lull_calls = lull_calls if lull_calls is not None else []

    def fake_lull(callback, quiet_seconds=3, max_wait_seconds=30):
        lull_calls.append(callback)

    return am.AssetManifest(
        client=client, config_dir=str(tmp_path), schedule_after_idle_lull=fake_lull)


def _reset_fetched_date(value=''):
    pan_app.settings.general['assets_manifest_fetched'] = value


def test_never_fetched_fetches_immediately(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    assert client.calls and client.calls[0][0] == am.MANIFEST_URL
    assert not done  # callback fires from the response, not yet


def test_fresh_cache_is_a_noop(tmp_path):
    _reset_fetched_date(date.today().isoformat())
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    assert client.calls == []
    assert done == [True]


def test_stale_cache_refetches_after_a_lull(tmp_path):
    old = (date.today() - timedelta(days=am._REFRESH_DAYS + 1)).isoformat()
    _reset_fetched_date(old)
    client = _FakeClient()
    lull_calls = []
    manifest = _make_manifest(tmp_path, client=client, lull_calls=lull_calls)
    manifest.ensure_fresh()
    assert client.calls == []  # not immediate
    assert len(lull_calls) == 1
    lull_calls[0]()  # simulate the lull passing
    assert client.calls and client.calls[0][0] == am.MANIFEST_URL


def test_successful_fetch_updates_cache_and_settings(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, callback, _error_callback = client.calls[0]
    callback(None, YAML_BYTES)
    assert done == [True]
    assert pan_app.settings.general['assets_manifest_fetched'] == date.today().isoformat()
    assert manifest.get('dictionary', 'de_DE')['folder'] == 'de'
    assert (tmp_path / am._CACHE_FILENAME).exists()


def test_failed_fetch_calls_on_done_without_updating_settings(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, _callback, error_callback = client.calls[0]
    error_callback(None, None)
    assert done == [True]
    assert pan_app.settings.general['assets_manifest_fetched'] == ''
    assert manifest.get('dictionary', 'de_DE') is None


def test_get_returns_none_when_never_fetched(tmp_path):
    manifest = _make_manifest(tmp_path)
    assert manifest.get('dictionary', 'de_DE') is None


def test_get_matches_bare_language_and_misses_unknown_locale(tmp_path):
    manifest = _make_manifest(tmp_path)
    manifest._data = yaml.safe_load(YAML_BYTES)
    assert manifest.get('dictionary', 'de')['folder'] == 'de'
    assert manifest.get('dictionary', 'fr_FR') is None
    assert manifest.get('thesaurus', 'de_DE') is None


def test_entry_shas_and_installed_asset_key():
    entry = {'folder': 'de', 'files': [{'name': 'a', 'sha': 'a1'}, {'name': 'b', 'sha': 'a2'}]}
    assert am.entry_shas(entry) == 'a1,a2'
    assert am.installed_asset_key('dictionary', 'de_DE') == 'dictionary.de_de'
