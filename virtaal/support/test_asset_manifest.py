#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for AssetManifest - a _FakeClient records .get() calls
instead of doing real network I/O, and schedule_after_idle_lull is
injected as a function that just calls back immediately, so no test
needs a real GLib main loop. _FakeRequest stands in for
httpclient.HTTPRequest (.status, .result_headers) since _on_fetched
now needs both to handle a 304/etag."""

import os
import time
from datetime import date, timedelta
from io import BytesIO

import yaml
from gi.repository import Gtk

from virtaal.common import pan_app
from virtaal.support import asset_manifest as am
from virtaal.support.httpclient import HTTPClient

YAML_DATA = {
    'dictionary': {
        'de_DE': {'folder': 'de', 'files': [
            {'name': 'de_DE_frami.aff', 'sha': 'a1'},
            {'name': 'de_DE_frami.dic', 'sha': 'a2'},
        ]},
    },
}
YAML_BYTES = yaml.safe_dump(YAML_DATA).encode('utf-8')


class _FakeRequest:
    def __init__(self, status, etag=None):
        self.status = status
        body = b'etag: "%s"\r\n' % etag.encode('ascii') if etag else b''
        self.result_headers = BytesIO(body)


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, etag=None, error_callback=None):
        self.calls.append((url, callback, etag, error_callback))


def _make_manifest(tmp_path, client=None, lull_calls=None):
    lull_calls = lull_calls if lull_calls is not None else []

    def fake_lull(callback, quiet_seconds=3, max_wait_seconds=30):
        lull_calls.append(callback)

    return am.AssetManifest(
        client=client, config_dir=str(tmp_path), schedule_after_idle_lull=fake_lull)


def _reset_fetched_date(value=''):
    pan_app.settings.general['assets_manifest_fetched'] = value
    pan_app.settings.general['assets_manifest_etag'] = ''


def test_never_fetched_fetches_immediately(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    assert client.calls and client.calls[0][0] == am.MANIFEST_URL
    assert client.calls[0][2] is None  # no local cache yet - no etag to send
    assert not done  # callback fires from the response, not yet


def test_fresh_cache_is_a_noop(tmp_path):
    _reset_fetched_date(date.today().isoformat())
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    assert client.calls == []
    assert done == [True]


def test_stale_cache_refetches_after_a_lull_with_the_stored_etag(tmp_path):
    old = (date.today() - timedelta(days=am._REFRESH_DAYS + 1)).isoformat()
    _reset_fetched_date(old)
    pan_app.settings.general['assets_manifest_etag'] = 'abc123'
    (tmp_path / am._CACHE_FILENAME).write_text(yaml.safe_dump(YAML_DATA))
    client = _FakeClient()
    lull_calls = []
    manifest = _make_manifest(tmp_path, client=client, lull_calls=lull_calls)
    manifest.ensure_fresh()
    assert client.calls == []  # not immediate
    assert len(lull_calls) == 1
    lull_calls[0]()  # simulate the lull passing
    assert client.calls and client.calls[0][0] == am.MANIFEST_URL
    assert client.calls[0][2] == 'abc123'


def test_successful_fetch_updates_cache_and_settings(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, callback, _etag, _error_callback = client.calls[0]
    callback(_FakeRequest(200, etag='v2'), YAML_BYTES)
    assert done == [True]
    assert pan_app.settings.general['assets_manifest_fetched'] == date.today().isoformat()
    assert pan_app.settings.general['assets_manifest_etag'] == 'v2'
    assert manifest.get('dictionary', 'de_DE')['folder'] == 'de'
    assert (tmp_path / am._CACHE_FILENAME).exists()


def test_not_modified_keeps_cached_data_and_only_bumps_fetched_date(tmp_path):
    _reset_fetched_date((date.today() - timedelta(days=am._REFRESH_DAYS + 1)).isoformat())
    pan_app.settings.general['assets_manifest_etag'] = 'abc123'
    (tmp_path / am._CACHE_FILENAME).write_text(yaml.safe_dump(YAML_DATA))
    client = _FakeClient()
    lull_calls = []
    manifest = _make_manifest(tmp_path, client=client, lull_calls=lull_calls)
    manifest.ensure_fresh()
    lull_calls[0]()
    _url, callback, _etag, _error_callback = client.calls[0]
    callback(_FakeRequest(304), b'')
    assert pan_app.settings.general['assets_manifest_fetched'] == date.today().isoformat()
    assert pan_app.settings.general['assets_manifest_etag'] == 'abc123'  # unchanged
    assert manifest.get('dictionary', 'de_DE')['folder'] == 'de'  # still from the cache


def test_failed_fetch_calls_on_done_without_updating_settings(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, _callback, _etag, error_callback = client.calls[0]
    error_callback(None, None)
    assert done == [True]
    assert pan_app.settings.general['assets_manifest_fetched'] == ''
    assert manifest.get('dictionary', 'de_DE') is None


def test_first_fetch_never_sends_a_stray_stored_etag(tmp_path):
    # No real cache file behind it (self._data is None) - an etag left
    # over in settings (e.g. the cache file went missing) must not be
    # sent, or a 304 would wrongly claim "unchanged" with nothing to
    # fall back on.
    _reset_fetched_date('')
    pan_app.settings.general['assets_manifest_etag'] = 'stale-stray-value'
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    manifest.ensure_fresh()
    assert client.calls[0][2] is None


def test_malformed_stored_date_is_treated_as_never_fetched(tmp_path):
    _reset_fetched_date('not-a-real-date')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    manifest.ensure_fresh()
    assert client.calls and client.calls[0][0] == am.MANIFEST_URL


def test_bad_response_body_falls_back_without_touching_data(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, callback, _etag, _error_callback = client.calls[0]
    callback(_FakeRequest(200, etag='v2'), b'not: valid: yaml: [')
    assert done == [True]
    assert pan_app.settings.general['assets_manifest_fetched'] == ''
    assert manifest.get('dictionary', 'de_DE') is None


def test_cache_write_failure_still_updates_data_and_calls_on_done(tmp_path):
    _reset_fetched_date('')
    client = _FakeClient()
    manifest = _make_manifest(tmp_path, client=client)
    # A file where the cache's own parent directory should be forces
    # os.makedirs() to fail, without needing to touch real permissions.
    blocking_file = tmp_path / 'not-a-dir'
    blocking_file.write_text('blocking')
    manifest._cache_path = str(blocking_file / am._CACHE_FILENAME)
    done = []
    manifest.ensure_fresh(on_done=lambda: done.append(True))
    _url, callback, _etag, _error_callback = client.calls[0]
    callback(_FakeRequest(200, etag='v2'), YAML_BYTES)
    assert done == [True]
    assert manifest.get('dictionary', 'de_DE')['folder'] == 'de'  # in-memory data still set


def test_default_config_dir_uses_pan_app(tmp_path):
    manifest = am.AssetManifest(client=_FakeClient())
    assert manifest._cache_path == os.path.join(pan_app.get_config_dir(), am._CACHE_FILENAME)


def test_default_client_is_a_real_http_client(tmp_path):
    _reset_fetched_date('')
    manifest = _make_manifest(tmp_path)  # no client injected
    manifest.ensure_fresh()
    assert isinstance(manifest._client, HTTPClient)


def _pump_until(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.05)


def test_real_schedule_after_idle_lull_fires_after_a_quiet_period():
    fired = []
    am.schedule_after_idle_lull(lambda: fired.append(True), quiet_seconds=0, max_wait_seconds=0)
    _pump_until(lambda: fired)
    assert fired == [True]
    # A second real call, now that the module-level activity tracker is
    # already installed, exercises its early-return path.
    am._ensure_activity_tracker_installed()


def test_real_schedule_after_idle_lull_polls_until_the_quiet_window_passes():
    am._last_activity[0] = time.monotonic()  # simulate activity right now
    fired = []
    am.schedule_after_idle_lull(lambda: fired.append(True), quiet_seconds=2, max_wait_seconds=10)
    _pump_until(lambda: fired, timeout=15)
    assert fired == [True]


def test_extract_etag_with_no_etag_header_returns_empty_string():
    assert am._extract_etag(_FakeRequest(200)) == ''


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
