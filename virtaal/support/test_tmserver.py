#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from cheroot import wsgi

from virtaal.support import tmserver
from virtaal.support.tmauth import TOKEN_ENV, TOKEN_HEADER

_servers = []
TOKEN = 'the-token'


@pytest.fixture(autouse=True)
def _stop_servers():
    yield
    while _servers:
        _servers.pop().stop()


def _start_server(db_path):
    """Start a TM server on a free port; returns (app, port)."""
    # The same cheroot server application.rest.run(server='cheroot')
    # builds, but one the test can stop.
    app = tmserver.TMServer(str(db_path), None, token=TOKEN, allowed_hosts=set())
    server = wsgi.Server(('127.0.0.1', 0), app.rest)
    # stop() waits for the serve loop's next wake-up, every 0.5s by default.
    server.expiration_interval = 0.01
    server.prepare()  # binds, so the port the OS picked is known
    port = server.bind_addr[1]
    threading.Thread(target=server.serve, daemon=True).start()
    _servers.append(server)
    _wait_for_port(port)
    return app, port


def _free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _wait_for_port(port, timeout=10):
    """Wait until the server on C{port} accepts connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection(('127.0.0.1', port), timeout=1).close()
            return
        except OSError:
            time.sleep(0.05)
    pytest.fail('nothing accepted connections on port %d within %ds' % (port, timeout))


def _request(port, method, path, data=None, headers=None, token=TOKEN):
    url = 'http://127.0.0.1:%d%s' % (port, path)
    body = data.encode('utf-8') if isinstance(data, str) else data
    headers = dict(headers or {})
    if token is not None:
        headers[TOKEN_HEADER] = token
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode('utf-8')


def _status(*args, **kwargs):
    """The HTTP status of a request that may fail."""
    try:
        return _request(*args, **kwargs)[0]
    except urllib.error.HTTPError as e:
        return e.code
    except ConnectionResetError:
        # Windows: the server answered 403 before reading the body.
        return 403


def _translate(port, source, slang, tlang):
    path = '/%s/%s/unit/%s' % (slang, tlang, quote(source, safe=''))
    return json.loads(_request(port, 'GET', path)[1])


def test_translate_unit_matches_a_non_ascii_source_exactly(tmp_path):
    # Real bug (#1405): PATH_INFO is PEP 3333 "native string" - UTF-8
    # bytes decoded as latin-1 - and selector.py used to match/route on
    # it directly without the required re-encode/re-decode round trip,
    # mangling any non-ASCII source string before it ever reached the
    # TM lookup. A Russian source used to score well under 100% against
    # its own exact match; confirmed 83% in the original report.
    app, port = _start_server(tmp_path / 'tm.db')
    source = 'Здравствуйте'
    app.tmdb.add_dict({'source': source, 'target': 'Hello', 'context': ''}, 'ru', 'en')

    matches = _translate(port, source, 'ru', 'en')

    assert matches, 'expected at least one match for an exact source string'
    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_translate_unit_still_matches_an_ascii_source(tmp_path):
    app, port = _start_server(tmp_path / 'tm.db')
    source = 'Hello world'
    app.tmdb.add_dict({'source': source, 'target': 'Bonjour le monde', 'context': ''}, 'en', 'fr')

    matches = _translate(port, source, 'en', 'fr')

    assert matches
    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_translate_unit_matches_a_source_containing_a_newline(tmp_path):
    # #4333: a multi-line source used to get HTTP 404 and no suggestions.
    app, port = _start_server(tmp_path / 'tm.db')
    source = 'Open the file\nnow please'
    app.tmdb.add_dict({'source': source, 'target': 'Maak die lêer\nnou oop', 'context': ''}, 'en', 'af')

    matches = _translate(port, source, 'en', 'af')

    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_translate_unit_matches_a_source_containing_a_slash(tmp_path):
    # #4373: cheroot leaves %2F encoded in PATH_INFO, so "Open/Save" was
    # looked up as "Open%2FSave".
    app, port = _start_server(tmp_path / 'tm.db')
    source = 'Open/Save'
    app.tmdb.add_dict({'source': source, 'target': 'Maak oop/Stoor', 'context': ''}, 'en', 'af')

    matches = _translate(port, source, 'en', 'af')

    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_translate_unit_matches_a_source_containing_a_percent_escape(tmp_path):
    # Decoded once: a literal "%2F" in the source stays "%2F".
    app, port = _start_server(tmp_path / 'tm.db')
    source = 'Size in KB%2Fs and 50% off'
    app.tmdb.add_dict({'source': source, 'target': 'x', 'context': ''}, 'en', 'af')

    matches = _translate(port, source, 'en', 'af')

    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def _decoded_path(monkeypatch, environ):
    monkeypatch.setattr(tmserver, 'request', SimpleNamespace(environ=environ))
    tmserver._decode_path_from_request_uri()
    return environ['PATH_INFO']


def test_decode_path_drops_the_query_string_and_the_script_name(monkeypatch):
    environ = {'REQUEST_URI': '/tm/en/af/unit/Open%2FSave?callback=x',
               'SCRIPT_NAME': '/tm', 'PATH_INFO': '/en/af/unit/Open%2FSave'}

    assert _decoded_path(monkeypatch, environ) == '/en/af/unit/Open/Save'


def test_decode_path_keeps_path_info_without_a_request_uri(monkeypatch):
    environ = {'PATH_INFO': '/en/af/unit/Open%2FSave'}

    assert _decoded_path(monkeypatch, environ) == '/en/af/unit/Open%2FSave'


@pytest.mark.parametrize('source', [
    'Press AND hold the power button',
    'Do NOT remove the cover while printing',
    'Place the printer NEAR the wall outlet',
])
def test_translate_unit_matches_a_source_with_a_capitalised_fts_operator(tmp_path, source):
    # #4332: an unquoted AND, NOT or NEAR made the full-text query fail.
    app, port = _start_server(tmp_path / 'tm.db')
    app.tmdb.add_dict({'source': source.lower(), 'target': 'x', 'context': ''}, 'en', 'af')

    matches = _translate(port, source, 'en', 'af')

    assert matches[0]['source'] == source.lower()


def test_add_unit_then_translate_unit_round_trips_over_http(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    status, body = _request(port, 'PUT', '/en/fr/unit/cat', json.dumps({'source': 'cat', 'target': 'chat'}))

    assert status == 200
    assert body == ''
    matches = _translate(port, 'cat', 'en', 'fr')
    assert matches[0]['target'] == 'chat'


def test_update_unit_changes_the_target(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')
    _request(port, 'PUT', '/en/fr/unit/dog', json.dumps({'source': 'dog', 'target': 'wrong'}))

    status, body = _request(port, 'POST', '/en/fr/unit/dog', json.dumps({'source': 'dog', 'target': 'chien'}))

    assert status == 200
    assert body == ''
    matches = _translate(port, 'dog', 'en', 'fr')
    assert any(m['target'] == 'chien' for m in matches)


def test_translate_unit_ignores_a_callback_parameter(tmp_path):
    app, port = _start_server(tmp_path / 'tm.db')
    app.tmdb.add_dict({'source': 'bird', 'target': 'oiseau', 'context': ''}, 'en', 'fr')

    status, body = _request(port, 'GET', '/en/fr/unit/bird?callback=myCallback')

    assert status == 200
    assert json.loads(body)[0]['target'] == 'oiseau'


ROUTES = [
    ('GET', '/en/fr/unit/cat', None),
    ('PUT', '/en/fr/unit/cat', json.dumps({'source': 'cat', 'target': 'chat'})),
    ('POST', '/en/fr/unit/cat', json.dumps({'source': 'cat', 'target': 'chat'})),
    ('DELETE', '/en/fr/unit/cat', None),
    ('GET', '/en/fr/store/import', None),
    ('PUT', '/en/fr/store/import.po', 'msgid "cat"\nmsgstr "chat"\n'),
    ('POST', '/en/fr/store/import', json.dumps([{'source': 'cat', 'target': 'chat', 'context': ''}])),
    ('DELETE', '/en/fr/store/import', None),
]


@pytest.mark.parametrize(('method', 'path', 'data'), ROUTES)
@pytest.mark.parametrize('token', [None, '', 'the-wrong-token', TOKEN + 'x', 'the-tokén'])
def test_every_route_refuses_a_request_without_the_token(tmp_path, method, path, data, token):
    app, port = _start_server(tmp_path / 'tm.db')

    assert _status(port, method, path, data, token=token) == 403
    assert app.tmdb.translate_unit('cat', 'en', 'fr') == []


@pytest.mark.parametrize(('method', 'path', 'data'), ROUTES)
def test_every_route_refuses_a_request_with_an_origin(tmp_path, method, path, data):
    app, port = _start_server(tmp_path / 'tm.db')

    assert _status(port, method, path, data, headers={'Origin': 'http://127.0.0.1:%d' % port}) == 403
    assert app.tmdb.translate_unit('cat', 'en', 'fr') == []


@pytest.mark.parametrize('host', ['example.com', 'example.com:%d', 'localhost.example.com', '127.0.0.1.example.com', ''])
def test_a_request_for_another_host_is_refused(tmp_path, host):
    app, port = _start_server(tmp_path / 'tm.db')
    app.tmdb.add_dict({'source': 'cat', 'target': 'chat', 'context': ''}, 'en', 'fr')
    host = host % port if '%d' in host else host

    assert _status(port, 'GET', '/en/fr/unit/cat', headers={'Host': host}) == 403


@pytest.mark.parametrize('host', ['localhost:%d', 'LOCALHOST:%d', '127.0.0.1:%d', '127.0.0.3:%d', '[::1]:%d', 'localhost'])
def test_a_request_for_a_loopback_host_is_answered(tmp_path, host):
    app, port = _start_server(tmp_path / 'tm.db')
    app.tmdb.add_dict({'source': 'cat', 'target': 'chat', 'context': ''}, 'en', 'fr')
    host = host % port if '%d' in host else host

    status, body = _request(port, 'GET', '/en/fr/unit/cat', headers={'Host': host})

    assert status == 200
    assert json.loads(body)[0]['target'] == 'chat'


def test_without_a_token_or_hosts_any_request_without_an_origin_is_answered(tmp_path):
    app = tmserver.TMServer(str(tmp_path / 'tm.db'), None)
    server = wsgi.Server(('127.0.0.1', 0), app.rest)
    server.expiration_interval = 0.01
    server.prepare()
    port = server.bind_addr[1]
    threading.Thread(target=server.serve, daemon=True).start()
    _servers.append(server)

    assert _status(port, 'GET', '/en/fr/unit/cat', token=None, headers={'Host': 'example.com'}) == 200
    assert _status(port, 'GET', '/en/fr/unit/cat', token=None, headers={'Origin': 'http://example.com'}) == 403


def test_virtaals_client_adds_a_store_and_looks_up_a_unit(tmp_path, monkeypatch):
    # The two requests Virtaal's local TM makes: add_store() on saving a
    # file, translate_unit() for suggestions.
    from virtaal.support.tmclient import TMClient

    _, port = _start_server(tmp_path / 'tm.db')
    client = TMClient('http://localhost:%d' % port, TOKEN)
    requests = []
    monkeypatch.setattr(client, 'add', requests.append)
    found = []

    def perform():
        request = requests.pop()
        request.curl.perform()
        request.handle_result()
        assert request.status == 200

    client.add_store('a.po', [{'source': 'cat', 'target': 'chat', 'context': ''}], 'en', 'fr')
    perform()
    client.translate_unit('cat', 'en', 'fr', callback=lambda widget, id, matches: found.append(matches))
    perform()

    assert found[0][0]['target'] == 'chat'


def test_a_request_for_the_bind_name_is_answered(tmp_path):
    app, port = _start_server(tmp_path / 'tm.db')
    app.allowed_hosts = {'tm.localdomain'}

    assert _status(port, 'GET', '/en/fr/unit/cat', headers={'Host': 'tm.localdomain:%d' % port}) == 200


def _resolves_to(monkeypatch, *addresses):
    def getaddrinfo(host, port):
        if not addresses:
            raise OSError('unknown host')
        return [(None, None, None, '', (address, 0)) for address in addresses]
    monkeypatch.setattr(tmserver.socket, 'getaddrinfo', getaddrinfo)


@pytest.mark.parametrize('bind', ['localhost', 'LocalHost', '127.0.0.1', '127.0.0.2', '::1'])
def test_binds_loopback_for_a_loopback_address(monkeypatch, bind):
    _resolves_to(monkeypatch)

    assert tmserver.binds_loopback(bind)


@pytest.mark.parametrize(('addresses', 'expected'), [
    (('127.0.0.1', '::1'), True),
    (('fe80::1%lo0', '::1'), False),
    (('127.0.0.1', '192.168.1.1'), False),
    ((), False),
])
def test_binds_loopback_resolves_a_name(monkeypatch, addresses, expected):
    _resolves_to(monkeypatch, *addresses)

    assert tmserver.binds_loopback('tm.localdomain') is expected


@pytest.mark.parametrize('bind', ['0.0.0.0', '::', '192.168.1.1'])
def test_binds_loopback_is_false_elsewhere(bind):
    assert not tmserver.binds_loopback(bind)


def test_forget_unit_returns_the_not_implemented_stub(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    status, body = _request(port, 'DELETE', '/en/fr/unit/cat')

    assert status == 200
    assert body == 'FIXME'


def test_add_store_then_translate_unit_finds_the_loaded_units(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')
    units = json.dumps([{'source': 'fish', 'target': 'poisson', 'context': ''}])

    status, body = _request(port, 'POST', '/en/fr/store/myimport', units)

    assert status == 200
    assert body == 'added 1 units from myimport'
    matches = _translate(port, 'fish', 'en', 'fr')
    assert matches[0]['target'] == 'poisson'


def test_upload_store_parses_an_uploaded_file(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')
    po_content = 'msgid "tree"\nmsgstr "arbre"\n'

    status, body = _request(port, 'PUT', '/en/fr/store/import.po', po_content)

    assert status == 200
    assert body == 'added 1 units from import.po'
    matches = _translate(port, 'tree', 'en', 'fr')
    assert matches[0]['target'] == 'arbre'


def test_get_store_stats_returns_the_not_implemented_stub(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    status, body = _request(port, 'GET', '/en/fr/store/myimport')

    assert status == 200
    assert body == 'FIXME'


def test_store_routes_accept_a_name_containing_a_newline(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    status, body = _request(port, 'GET', '/en/fr/store/' + quote('my\nimport', safe=''))

    assert status == 200
    assert body == 'FIXME'


def test_forget_store_returns_the_not_implemented_stub(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    status, body = _request(port, 'DELETE', '/en/fr/store/myimport')

    assert status == 200
    assert body == 'FIXME'


def test_unknown_path_returns_404(tmp_path):
    _, port = _start_server(tmp_path / 'tm.db')

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request(port, 'GET', '/nonexistent')

    assert excinfo.value.code == 404


# __init__()'s bytes-tmdbfile decode and tmfiles-loading branches #

def test_init_decodes_a_bytes_tmdbfile(tmp_path):
    db_path = str(tmp_path / 'tm.db').encode(sys.getfilesystemencoding())

    server = tmserver.TMServer(db_path, None)

    assert server.tmdb.add_dict({'source': 'cat', 'target': 'chat', 'context': ''}, 'en', 'fr') is None
    assert server.tmdb.translate_unit('cat', 'en', 'fr')


def test_init_loads_a_single_tm_file(tmp_path):
    po_path = tmp_path / 'seed.po'
    po_path.write_text('msgid "cat"\nmsgstr "chat"\n')

    server = tmserver.TMServer(str(tmp_path / 'tm.db'), str(po_path), source_lang='en', target_lang='fr')

    matches = server.tmdb.translate_unit('cat', 'en', 'fr')
    assert matches[0]['target'] == 'chat'


def test_init_loads_a_list_of_tm_files(tmp_path):
    po1 = tmp_path / 'a.po'
    po1.write_text('msgid "cat"\nmsgstr "chat"\n')
    po2 = tmp_path / 'b.po'
    po2.write_text('msgid "dog"\nmsgstr "chien"\n')

    server = tmserver.TMServer(str(tmp_path / 'tm.db'), [str(po1), str(po2)], source_lang='en', target_lang='fr')

    assert server.tmdb.translate_unit('cat', 'en', 'fr')[0]['target'] == 'chat'
    assert server.tmdb.translate_unit('dog', 'en', 'fr')[0]['target'] == 'chien'


# build_parser() #

def test_build_parser_defaults():
    args = tmserver.build_parser().parse_args([])

    assert args.tmdbfile == ':memory:'
    assert args.tmfiles is None
    assert args.bind == 'localhost'
    assert args.port == 8888
    assert args.max_candidates == 3
    assert args.min_similarity == 75
    assert args.max_length == 1000
    assert args.debug is False


def test_build_parser_parses_provided_options():
    args = tmserver.build_parser().parse_args([
        '-d', 'my.db', '-f', 'a.po', '-f', 'b.po', '-s', 'en', '-t', 'fr',
        '-b', '0.0.0.0', '-p', '9999',
        '--max-candidates', '5', '--min-similarity', '50', '--max-length', '500',
        '--debug',
    ])

    assert args.tmdbfile == 'my.db'
    assert args.tmfiles == ['a.po', 'b.po']
    assert args.source_lang == 'en'
    assert args.target_lang == 'fr'
    assert args.bind == '0.0.0.0'
    assert args.port == 9999
    assert args.max_candidates == 5
    assert args.min_similarity == 50
    assert args.max_length == 500
    assert args.debug is True


# main() - in-process, with the actual server bind/listen stubbed out #

def test_main_runs_the_server_with_the_parsed_bind_and_port(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(sys, 'argv', ['tmserver', '-d', str(tmp_path / 'tm.db'), '-b', '127.0.0.1', '-p', '1234'])
    monkeypatch.setattr(tmserver.Bottle, 'run', lambda self, **kwargs: calls.append(kwargs))

    tmserver.main()

    assert calls == [{'host': '127.0.0.1', 'port': 1234, 'server': 'cheroot', 'quiet': True}]


def test_main_uses_a_more_verbose_format_and_keeps_cheroot_noisy_when_debugging(monkeypatch, tmp_path):
    run_calls = []
    basic_config_calls = []
    monkeypatch.setattr(sys, 'argv', ['tmserver', '-d', str(tmp_path / 'tm.db'), '--debug'])
    monkeypatch.setattr(tmserver.Bottle, 'run', lambda self, **kwargs: run_calls.append(kwargs))
    monkeypatch.setattr(tmserver.logging, 'basicConfig', lambda **kwargs: basic_config_calls.append(kwargs))

    tmserver.main()

    assert basic_config_calls[0]['level'] == tmserver.logging.DEBUG
    assert '%(funcName)s' in basic_config_calls[0]['format']
    assert run_calls == [{'host': 'localhost', 'port': 8888, 'server': 'cheroot', 'quiet': False}]


def test_main_swallows_a_keyboard_interrupt_from_the_server(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['tmserver', '-d', str(tmp_path / 'tm.db')])

    def raise_interrupt(self, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(tmserver.Bottle, 'run', raise_interrupt)

    tmserver.main()  # must not raise


def _main_server(monkeypatch, tmp_path, *argv):
    """The TMServer main() builds for C{argv}, without serving."""
    built = []
    real = tmserver.TMServer
    monkeypatch.setattr(tmserver, 'TMServer', lambda *args, **kwargs: built.append(real(*args, **kwargs)) or built[-1])
    monkeypatch.setattr(tmserver.Bottle, 'run', lambda self, **kwargs: None)
    monkeypatch.setattr(sys, 'argv', ['tmserver', '-d', str(tmp_path / 'tm.db'), *argv])
    tmserver.main()
    return built[0]


def test_main_takes_the_token_from_the_environment(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(TOKEN_ENV, 'from-virtaal')

    server = _main_server(monkeypatch, tmp_path)

    assert server.token == 'from-virtaal'
    assert 'from-virtaal' not in capsys.readouterr().err


def test_main_makes_and_prints_a_token_without_one(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(TOKEN_ENV, raising=False)

    server = _main_server(monkeypatch, tmp_path)

    assert len(server.token) >= 32
    assert capsys.readouterr().err == '%s: %s\n' % (TOKEN_HEADER, server.token)
    assert _main_server(monkeypatch, tmp_path).token != server.token


@pytest.mark.parametrize('bind', ['localhost', '127.0.0.1', '127.0.0.2', '::1'])
def test_main_answers_only_loopback_names_when_bound_to_loopback(monkeypatch, tmp_path, bind):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)

    server = _main_server(monkeypatch, tmp_path, '-b', bind)

    assert server.allowed_hosts == {bind}


@pytest.mark.parametrize('bind', ['0.0.0.0', '192.168.1.1', 'tm.example.org'])
def test_main_answers_any_host_name_when_bound_elsewhere(monkeypatch, tmp_path, bind):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    _resolves_to(monkeypatch, '192.0.2.1')

    server = _main_server(monkeypatch, tmp_path, '-b', bind)

    assert server.allowed_hosts is None


def test_main_serves_over_http_as_the_subprocess_localtm_spawns(tmp_path):
    # localtm.py always launches tmserver this way ("-m
    # virtaal.support.tmserver"), never by importing TMServer directly -
    # this is the one test that actually goes through main()'s argument
    # parsing and application.rest.run() call, not just the class.
    port = _free_port()
    command = [
        sys.executable, '-m', 'virtaal.support.tmserver',
        '-b', '127.0.0.1', '-p', str(port), '-d', str(tmp_path / 'tm.db'),
    ]
    proc = subprocess.Popen(command, env=dict(os.environ, **{TOKEN_ENV: TOKEN}))
    try:
        _wait_for_port(port)
        assert _status(port, 'GET', '/tmserver/en/fr/unit/owl', token=None) == 403
        _request(port, 'PUT', '/tmserver/en/fr/unit/owl', json.dumps({'source': 'owl', 'target': 'hibou'}))

        status, body = _request(port, 'GET', '/tmserver/en/fr/unit/owl')

        assert status == 200
        assert json.loads(body)[0]['target'] == 'hibou'
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
