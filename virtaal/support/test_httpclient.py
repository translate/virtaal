#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins
import os
import sys
from types import SimpleNamespace

import pycurl
from gi.repository import GLib

from virtaal.support.httpclient import HTTPClient, HTTPRequest, RESTRequest

# RESTRequest: URL-building around an optional id and query params.
# get_effective_url() reflects the built URL directly from the real
# curl handle, even before any transfer is ever performed.

def test_restrequest_leaves_the_url_unchanged_without_an_id_or_params():
    req = RESTRequest('http://example.com/unit', '')
    assert req.get_effective_url() == 'http://example.com/unit'


def test_restrequest_appends_the_id_url_encoded():
    req = RESTRequest('http://example.com/unit', 'hello world')
    assert req.get_effective_url() == 'http://example.com/unit/hello%20world'


def test_restrequest_appends_params_as_a_query_string():
    req = RESTRequest('http://example.com/unit', '', params={'a': '1'})
    assert req.get_effective_url() == 'http://example.com/unit?a=1'


def test_restrequest_appends_both_an_id_and_params():
    req = RESTRequest('http://example.com/unit', 'x', params={'a': '1'})
    assert req.get_effective_url() == 'http://example.com/unit/x?a=1'


# HTTPRequest.handle_result(): status-code -> signal dispatch.
# pycurl.Curl doesn't allow shadowing its own methods on an instance
# (only adding genuinely new attributes, as the real code itself does
# with `self.curl.request = self`), so swap the whole curl attribute
# for a stub instead.

def _signal_after_status(status):
    req = HTTPRequest('http://example.com')
    req.curl = SimpleNamespace(getinfo=lambda opt: status)
    fired = []
    for signal in ('http-success', 'http-redirect', 'http-client-error', 'http-server-error'):
        req.connect(signal, lambda r, arg, signal=signal: fired.append(signal))
    req.handle_result()
    return fired


def test_handle_result_emits_http_success_for_2xx():
    assert _signal_after_status(200) == ['http-success']


def test_handle_result_emits_http_redirect_for_3xx():
    assert _signal_after_status(301) == ['http-redirect']


def test_handle_result_emits_http_client_error_for_4xx():
    assert _signal_after_status(404) == ['http-client-error']


def test_handle_result_emits_http_server_error_for_5xx():
    assert _signal_after_status(500) == ['http-server-error']


def test_handle_result_emits_nothing_for_an_unrecognized_status():
    assert _signal_after_status(0) == []


def test_get_effective_url_reads_it_from_curl():
    req = HTTPRequest('http://example.com')
    req.curl = SimpleNamespace(getinfo=lambda opt: 'http://example.com/redirected')

    assert req.get_effective_url() == 'http://example.com/redirected'


# HTTPClient.add()/run(): the request queue and its GLib idle-driven
# pump - real requests are pure-Python pycurl handles, so a fake
# CurlMulti isolates this state machine from any actual network I/O.

class _FakeCurlMulti:
    def __init__(self):
        self.added = []
        self.removed = []
        self.perform_result = (pycurl.E_MULTI_OK, 0)
        self.info_read_result = (0, [], [])

    def add_handle(self, handle):
        self.added.append(handle)

    def remove_handle(self, handle):
        self.removed.append(handle)

    def perform(self):
        return self.perform_result

    def info_read(self):
        return self.info_read_result


def _client():
    client = HTTPClient()
    client.curl = _FakeCurlMulti()
    return client


class _FakeRequest:
    # SimpleNamespace defines __eq__, which makes it unhashable - these
    # go into HTTPClient.requests, a real set.
    def __init__(self, curl=None, handle_result=None):
        self.curl = curl
        if handle_result is not None:
            self.handle_result = handle_result


def test_add_declines_once_the_queue_is_full(monkeypatch):
    monkeypatch.setattr(GLib, 'timeout_add', lambda interval, func: None)
    client = _client()
    client.requests = {object() for _ in range(16)}
    request = _FakeRequest(curl='handle')

    client.add(request)

    assert request not in client.requests
    assert client.curl.added == []


def test_add_queues_the_request_and_starts_the_pump(monkeypatch):
    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda interval, func: scheduled.append((interval, func)))
    client = _client()
    request = _FakeRequest(curl='handle')

    client.add(request)

    assert request in client.requests
    assert client.curl.added == ['handle']
    assert client.running is True
    assert scheduled == [(100, client.perform)]


def test_run_does_not_schedule_a_second_timeout_while_already_running(monkeypatch):
    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda interval, func: scheduled.append(func))
    client = _client()

    client.run()
    client.run()

    assert len(scheduled) == 1


# HTTPClient.perform(): drains completed/failed handles and reports
# whether GLib should keep calling it back.

def test_perform_stops_the_pump_once_all_handles_are_done():
    client = _client()
    client.running = True
    client.curl.perform_result = (pycurl.E_MULTI_OK, 0)

    assert client.perform() is False
    assert client.running is False


def test_perform_keeps_the_pump_running_while_handles_remain():
    client = _client()
    client.running = True
    client.curl.perform_result = (pycurl.E_CALL_MULTI_PERFORM, 2)

    assert client.perform() is True
    assert client.running is True


def test_perform_closes_a_completed_request():
    client = _client()
    client.running = True
    results = []
    request = _FakeRequest(handle_result=lambda: results.append('done'))
    handle = SimpleNamespace(request=request)
    client.requests = {request}
    client.curl.info_read_result = (0, [handle], [])

    client.perform()

    assert results == ['done']
    assert request not in client.requests
    assert handle in client.curl.removed


def test_perform_closes_a_failed_request_without_calling_handle_result():
    client = _client()
    client.running = True
    request = _FakeRequest(handle_result=lambda: (_ for _ in ()).throw(
        AssertionError('a failed request should not be treated as completed')))
    handle = SimpleNamespace(request=request)
    client.requests = {request}
    client.curl.info_read_result = (0, [], [(handle, 42, 'timed out')])

    client.perform()

    assert request not in client.requests
    assert handle in client.curl.removed


# HTTPClient.get()

def test_get_queues_a_request_and_wires_only_the_given_callbacks():
    client = _client()
    added = []
    client.add = lambda request: added.append(request)
    success_calls = []
    error_calls = []

    client.get('http://example.com', callback=lambda r, v: success_calls.append(v))

    request = added[0]
    request.emit('http-success', b'ok')
    request.emit('http-redirect', b'ok')
    assert success_calls == [b'ok', b'ok']

    request.emit('http-client-error', 404)  # must not raise with no error_callback


def test_get_wires_the_error_callback_to_both_client_and_server_errors():
    client = _client()
    added = []
    client.add = lambda request: added.append(request)
    errors = []

    client.get('http://example.com', callback=None, error_callback=lambda r, v: errors.append(v))

    request = added[0]
    request.emit('http-client-error', 404)
    request.emit('http-server-error', 500)
    assert errors == [404, 500]


def test_get_sends_an_if_none_match_header_when_an_etag_is_given():
    client = _client()
    added = []
    client.add = lambda request: added.append(request)

    client.get('http://example.com', callback=None, etag='abc123')

    assert added[0].headers == ['If-None-Match: "abc123"']


# set_virtaal_useragent()

def test_set_virtaal_useragent_is_idempotent_once_already_set():
    client = HTTPClient()
    client.user_agent = 'Virtaal/1.0 (custom)'

    client.set_virtaal_useragent()

    assert client.user_agent == 'Virtaal/1.0 (custom)'


def test_set_virtaal_useragent_reads_the_distro_from_os_release(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'linux')
    os_release = tmp_path / 'os-release'
    os_release.write_text('NAME="Ubuntu"\nVERSION="22.04 LTS"\n')
    real_open = builtins.open
    monkeypatch.setattr(os.path, 'isfile', lambda path: path == '/etc/os-release')
    monkeypatch.setattr(builtins, 'open', lambda path, *a, **k: real_open(str(os_release)))
    client = HTTPClient()

    client.set_virtaal_useragent()

    assert 'Ubuntu' in client.user_agent
    assert '22.04 LTS' in client.user_agent
    assert client.user_agent.startswith('Virtaal/')


def test_set_virtaal_useragent_survives_a_malformed_release_file(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(os.path, 'isfile', lambda path: path == '/etc/os-release')
    monkeypatch.setattr(builtins, 'open', lambda path, *a, **k: (_ for _ in ()).throw(OSError('boom')))
    client = HTTPClient()

    client.set_virtaal_useragent()  # must not raise

    assert client.user_agent.startswith('Virtaal/')


def test_set_virtaal_useragent_maps_a_known_windows_version(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'getwindowsversion', lambda: (10, 0, 19045), raising=False)
    client = HTTPClient()

    client.set_virtaal_useragent()

    assert 'Windows 10' in client.user_agent


def test_set_virtaal_useragent_on_an_unrecognized_windows_version_omits_the_name(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'getwindowsversion', lambda: (99, 9, 0), raising=False)
    client = HTTPClient()

    client.set_virtaal_useragent()  # must not raise

    assert client.user_agent.startswith('Virtaal/')


def test_set_virtaal_useragent_on_macos_includes_the_release(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    client = HTTPClient()

    client.set_virtaal_useragent()

    assert client.user_agent.startswith('Virtaal/')
    assert 'darwin' in client.user_agent
