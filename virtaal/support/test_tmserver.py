#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import functools
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

from virtaal.support import tmserver


def _start_server(db_path, port):
    app = tmserver.TMServer(str(db_path), None)
    run = functools.partial(app.rest.run, host='localhost', port=port, server='cheroot', quiet=True)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(0.5)  # give cheroot a moment to actually bind before the first request
    return app


def _request(port, method, path, data=None):
    url = 'http://localhost:%d%s' % (port, path)
    body = data.encode('utf-8') if isinstance(data, str) else data
    req = urllib.request.Request(url, data=body, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode('utf-8')


def _translate(port, source, slang, tlang):
    url = 'http://localhost:%d/%s/%s/unit/%s' % (port, slang, tlang, quote(source, safe=''))
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode('utf-8'))


def test_translate_unit_matches_a_non_ascii_source_exactly(tmp_path):
    # Real bug (#1405): PATH_INFO is PEP 3333 "native string" - UTF-8
    # bytes decoded as latin-1 - and selector.py used to match/route on
    # it directly without the required re-encode/re-decode round trip,
    # mangling any non-ASCII source string before it ever reached the
    # TM lookup. A Russian source used to score well under 100% against
    # its own exact match; confirmed 83% in the original report.
    port = 18765
    app = _start_server(tmp_path / 'tm.db', port)
    source = 'Здравствуйте'
    app.tmdb.add_dict({'source': source, 'target': 'Hello', 'context': ''}, 'ru', 'en')

    matches = _translate(port, source, 'ru', 'en')

    assert matches, 'expected at least one match for an exact source string'
    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_translate_unit_still_matches_an_ascii_source(tmp_path):
    port = 18766
    app = _start_server(tmp_path / 'tm.db', port)
    source = 'Hello world'
    app.tmdb.add_dict({'source': source, 'target': 'Bonjour le monde', 'context': ''}, 'en', 'fr')

    matches = _translate(port, source, 'en', 'fr')

    assert matches
    assert matches[0]['source'] == source
    assert matches[0]['quality'] == 100.0


def test_add_unit_then_translate_unit_round_trips_over_http(tmp_path):
    port = 18767
    _start_server(tmp_path / 'tm.db', port)

    status, body = _request(port, 'PUT', '/en/fr/unit/cat', json.dumps({'source': 'cat', 'target': 'chat'}))

    assert status == 200
    assert body == ''
    matches = _translate(port, 'cat', 'en', 'fr')
    assert matches[0]['target'] == 'chat'


def test_update_unit_changes_the_target(tmp_path):
    port = 18768
    _start_server(tmp_path / 'tm.db', port)
    _request(port, 'PUT', '/en/fr/unit/dog', json.dumps({'source': 'dog', 'target': 'wrong'}))

    status, body = _request(port, 'POST', '/en/fr/unit/dog', json.dumps({'source': 'dog', 'target': 'chien'}))

    assert status == 200
    assert body == ''
    matches = _translate(port, 'dog', 'en', 'fr')
    assert any(m['target'] == 'chien' for m in matches)


def test_translate_unit_wraps_response_in_jsonp_callback(tmp_path):
    port = 18769
    app = _start_server(tmp_path / 'tm.db', port)
    app.tmdb.add_dict({'source': 'bird', 'target': 'oiseau', 'context': ''}, 'en', 'fr')

    status, body = _request(port, 'GET', '/en/fr/unit/bird?callback=myCallback')

    assert status == 200
    assert body.startswith('myCallback(')
    assert body.endswith(')')
    assert json.loads(body[len('myCallback('):-1])[0]['target'] == 'oiseau'


def test_forget_unit_returns_the_not_implemented_stub(tmp_path):
    port = 18770
    _start_server(tmp_path / 'tm.db', port)

    status, body = _request(port, 'DELETE', '/en/fr/unit/cat')

    assert status == 200
    assert body == 'FIXME'


def test_add_store_then_translate_unit_finds_the_loaded_units(tmp_path):
    port = 18771
    _start_server(tmp_path / 'tm.db', port)
    units = json.dumps([{'source': 'fish', 'target': 'poisson', 'context': ''}])

    status, body = _request(port, 'POST', '/en/fr/store/myimport', units)

    assert status == 200
    assert body == 'added 1 units from myimport'
    matches = _translate(port, 'fish', 'en', 'fr')
    assert matches[0]['target'] == 'poisson'


def test_upload_store_parses_an_uploaded_file(tmp_path):
    port = 18772
    _start_server(tmp_path / 'tm.db', port)
    po_content = 'msgid "tree"\nmsgstr "arbre"\n'

    status, body = _request(port, 'PUT', '/en/fr/store/import.po', po_content)

    assert status == 200
    assert body == 'added 1 units from import.po'
    matches = _translate(port, 'tree', 'en', 'fr')
    assert matches[0]['target'] == 'arbre'


def test_get_store_stats_returns_the_not_implemented_stub(tmp_path):
    port = 18773
    _start_server(tmp_path / 'tm.db', port)

    status, body = _request(port, 'GET', '/en/fr/store/myimport')

    assert status == 200
    assert body == 'FIXME'


def test_forget_store_returns_the_not_implemented_stub(tmp_path):
    port = 18774
    _start_server(tmp_path / 'tm.db', port)

    status, body = _request(port, 'DELETE', '/en/fr/store/myimport')

    assert status == 200
    assert body == 'FIXME'


def test_unknown_path_returns_404(tmp_path):
    port = 18775
    _start_server(tmp_path / 'tm.db', port)

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


def test_main_serves_over_http_as_the_subprocess_localtm_spawns(tmp_path):
    # localtm.py always launches tmserver this way ("-m
    # virtaal.support.tmserver"), never by importing TMServer directly -
    # this is the one test that actually goes through main()'s argument
    # parsing and application.rest.run() call, not just the class.
    port = 18776
    command = [
        sys.executable, '-m', 'virtaal.support.tmserver',
        '-b', 'localhost', '-p', str(port), '-d', str(tmp_path / 'tm.db'),
    ]
    proc = subprocess.Popen(command, env=os.environ.copy())
    try:
        for _ in range(50):
            try:
                _request(port, 'PUT', '/tmserver/en/fr/unit/owl', json.dumps({'source': 'owl', 'target': 'hibou'}))
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.1)
        else:
            pytest.fail('tmserver subprocess never came up')

        status, body = _request(port, 'GET', '/tmserver/en/fr/unit/owl')

        assert status == 200
        assert json.loads(body)[0]['target'] == 'hibou'
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
