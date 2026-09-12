#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import threading
import time
import urllib.request
from urllib.parse import quote

from virtaal.support import tmserver, wsgi


def _start_server(db_path, port):
    app = tmserver.TMServer(str(db_path), None)
    thread = threading.Thread(target=wsgi.launch_server, args=('localhost', port, app.rest), daemon=True)
    thread.start()
    time.sleep(0.5)  # give cheroot a moment to actually bind before the first request
    return app


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
