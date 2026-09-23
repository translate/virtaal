#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json

import pycurl

from virtaal.support import tmclient
from virtaal.support.tmclient import TMClient


def test_forget_unit_builds_the_url_without_raising():
    """forget_unit()'s URL format string had 2 placeholders but a
    3-value tuple (self.user_agent left in by mistake - it's already
    passed separately as the user_agent= kwarg) - raised TypeError
    immediately on every call, before any network I/O."""
    client = TMClient('http://example.com')
    client.forget_unit('unit source', 'en', 'af')


class _FakeCurl:
    def __init__(self):
        self.opts = {}

    def setopt(self, key, value):
        self.opts[key] = value


class _FakeRequest:
    def __init__(self, url, id, method='GET', data=None, headers=None, user_agent=None, params=None):
        self.url = url
        self.id = id
        self.method = method
        self.data = data
        self.headers = headers
        self.user_agent = user_agent
        self.params = params
        self.curl = _FakeCurl()
        self.connected = []

    def connect(self, signal, handler):
        self.connected.append((signal, handler))
        return len(self.connected)


def _make_client(monkeypatch):
    monkeypatch.setattr(tmclient, 'RESTRequest', _FakeRequest)
    client = TMClient('http://example.com')
    client.user_agent = 'Virtaal/test'
    requests = []
    monkeypatch.setattr(client, 'add', lambda request: requests.append(request))
    return client, requests


def _fire_callback(request, payload):
    signal, handler = request.connected[0]
    assert signal == 'http-success'
    handler(request, json.dumps(payload).encode())


def test_translate_unit_builds_a_get_request(monkeypatch):
    client, requests = _make_client(monkeypatch)

    client.translate_unit('hello', 'en', 'af', params={'max': '3'})

    request = requests[0]
    assert request.url == 'http://example.com/en/af/unit'
    assert request.method == 'GET'
    assert request.id == 'hello'
    assert request.user_agent == 'Virtaal/test'
    assert request.params == {'max': '3'}
    assert request.curl.opts[pycurl.TIMEOUT] == 30


def test_translate_unit_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []

    client.translate_unit('hello', 'en', 'af', callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'target': 'hallo'})
    assert calls == [('hello', {'target': 'hallo'})]


def test_add_unit_builds_a_put_request_with_the_unit_as_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    unit = {'source': 'hello', 'target': 'hallo'}

    client.add_unit(unit, 'en', 'af')

    request = requests[0]
    assert request.url == 'http://example.com/en/af/unit'
    assert request.method == 'PUT'
    assert request.id == 'hello'
    assert request.data == json.dumps(unit)
    assert request.user_agent == 'Virtaal/test'


def test_add_unit_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []

    client.add_unit({'source': 'hello'}, 'en', 'af',
                     callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('hello', {'status': 'ok'})]


def test_update_unit_builds_a_post_request_with_the_unit_as_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    unit = {'source': 'hello', 'target': 'hallo'}

    client.update_unit(unit, 'en', 'af')

    request = requests[0]
    assert request.url == 'http://example.com/en/af/unit'
    assert request.method == 'POST'
    assert request.id == 'hello'
    assert request.data == json.dumps(unit)
    assert request.user_agent == 'Virtaal/test'


def test_update_unit_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []

    client.update_unit({'source': 'hello'}, 'en', 'af',
                        callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('hello', {'status': 'ok'})]


def test_forget_unit_builds_a_delete_request(monkeypatch):
    client, requests = _make_client(monkeypatch)

    client.forget_unit('hello', 'en', 'af')

    request = requests[0]
    assert request.url == 'http://example.com/en/af/unit'
    assert request.method == 'DELETE'
    assert request.id == 'hello'
    assert request.user_agent == 'Virtaal/test'


def test_forget_unit_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []

    client.forget_unit('hello', 'en', 'af',
                        callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('hello', {'status': 'ok'})]


class _FakeStore:
    def __init__(self, filename, content='store content'):
        self.filename = filename
        self._content = content

    def __str__(self):
        return self._content


def test_get_store_stats_builds_a_get_request(monkeypatch):
    client, requests = _make_client(monkeypatch)
    store = _FakeStore('test.po')

    client.get_store_stats(store)

    request = requests[0]
    assert request.url == 'http://example.com/store'
    assert request.method == 'GET'
    assert request.id == 'test.po'
    assert request.user_agent == 'Virtaal/test'


def test_get_store_stats_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []
    store = _FakeStore('test.po')

    client.get_store_stats(store, callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'total': 10})
    assert calls == [('test.po', {'total': 10})]


def test_upload_store_builds_a_put_request_with_the_stores_text(monkeypatch):
    client, requests = _make_client(monkeypatch)
    store = _FakeStore('test.po')

    client.upload_store(store, 'en', 'af')

    request = requests[0]
    assert request.url == 'http://example.com/en/af/store'
    assert request.method == 'PUT'
    assert request.id == 'test.po'
    assert request.data == 'store content'
    assert request.user_agent == 'Virtaal/test'


def test_upload_store_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []
    store = _FakeStore('test.po')

    client.upload_store(store, 'en', 'af', callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('test.po', {'status': 'ok'})]


def test_add_store_builds_a_post_request_with_the_store_as_json(monkeypatch):
    client, requests = _make_client(monkeypatch)

    client.add_store('test.po', {'units': []}, 'en', 'af')

    request = requests[0]
    assert request.url == 'http://example.com/en/af/store'
    assert request.method == 'POST'
    assert request.id == 'test.po'
    assert request.data == json.dumps({'units': []})
    assert request.user_agent == 'Virtaal/test'


def test_forget_store_builds_a_delete_request(monkeypatch):
    client, requests = _make_client(monkeypatch)
    store = _FakeStore('test.po')

    client.forget_store(store)

    request = requests[0]
    assert request.url == 'http://example.com/store'
    assert request.method == 'DELETE'
    assert request.id == 'test.po'
    assert request.user_agent == 'Virtaal/test'


def test_forget_store_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []
    store = _FakeStore('test.po')

    client.forget_store(store, callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('test.po', {'status': 'ok'})]


def test_add_store_wires_the_callback_with_decoded_json(monkeypatch):
    client, requests = _make_client(monkeypatch)
    calls = []

    client.add_store('test.po', {'units': []}, 'en', 'af',
                      callback=lambda widget, id, data: calls.append((id, data)))

    _fire_callback(requests[0], {'status': 'ok'})
    assert calls == [('test.po', {'status': 'ok'})]
