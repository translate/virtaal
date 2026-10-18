#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fuzz the translation memory, machine translation and glossary download
services with a local server that stands in for each of them.

Each service gets a sweep (service-<name>): one case per corpus value as
a suggestion (or a downloaded term), and one per bad reply - not JSON,
truncated, empty, the wrong shape, 5 MB, slow, 404, 500, a redirect
loop, invalid UTF-8. A case fails on an exception, a logged error, a
critical, or a suggestion whose markup characters don't all show as
text. service-localtm fills the local TM with corpus translations
instead.
"""

import http.server
import json
import os
import threading
import time
import xmlrpc.client
from urllib.parse import unquote

from corpus import CORPUS, short

# Not autoterm: Virtaal always turns it off, its one URL having been dead for years.
SERVICES = ('amagama', 'remotetm', 'apertium', 'moses', 'google', 'pontoon', 'localtm')
SLOW_SECONDS = 35  # longer than the clients' 30 s timeout

BAD_REPLIES = [
    ('not JSON', 200, b'<html><body>Service Unavailable</body></html>', 'text/html'),
    ('truncated', 200, None, None),
    ('empty body', 200, b'', 'application/json'),
    ('wrong shape', 200, b'{"unexpected": [1, 2, 3]}', 'application/json'),
    ('null', 200, b'null', 'application/json'),
    ('5 MB', 200, None, None),
    ('invalid UTF-8', 200, b'\xff\xfe\xfa{"x": "\xc3("}', 'application/json'),
    ('404', 404, b'Not Found', 'text/plain'),
    ('500', 500, b'Internal Server Error', 'text/plain'),
    ('redirect loop', 302, b'', None),
    ('slow', 200, None, None),
]


class Mock:
    """What the server answers; the sweep changes it between cases."""
    service = None
    value = 'Stoor die lêer'
    reply = None  # a BAD_REPLIES name, or None to answer with value
    requests = 0


def good_body(service, path, value):
    if service in ('amagama', 'remotetm'):
        query = unquote(path.rsplit('/unit/', 1)[-1].split('?')[0]) if '/unit/' in path else 'x'
        return json.dumps([{'source': query, 'target': value, 'quality': 90, 'rank': 90}]).encode(), \
            'application/json'
    if service == 'apertium':
        if 'listPairs' in path:
            return json.dumps({'responseStatus': 200, 'responseData': [
                {'sourceLanguage': 'en', 'targetLanguage': 'af'}]}).encode(), 'application/json'
        return json.dumps({'responseStatus': 200, 'responseData': {'translatedText': value}}).encode(), \
            'application/json'
    if service == 'google':
        if '/languages' in path:
            return json.dumps({'data': {'languages': [{'language': 'en'}, {'language': 'af'}]}}).encode(), \
                'application/json'
        return json.dumps({'data': {'translations': [{'translatedText': value}]}}).encode(), 'application/json'
    if service == 'moses':
        return xmlrpc.client.dumps(({'text': value},), methodresponse=True).encode('utf-8', 'surrogatepass'), \
            'text/xml'
    if service == 'pontoon':
        from xml.sax.saxutils import escape
        return ('<?xml version="1.0" encoding="UTF-8"?><martif type="TBX" xml:lang="en"><text><body>'
                '<termEntry><langSet xml:lang="en"><tig><term>file</term></tig></langSet>'
                '<langSet xml:lang="af"><tig><term>%s</term></tig></langSet></termEntry>'
                '</body></text></martif>' % escape(value)).encode('utf-8', 'surrogatepass'), 'application/x-tbx'
    if service == 'autoterm':
        from translate.storage import po
        store = po.pofile()
        store.updateheader(add=True, Language='af')
        store.addsourceunit('file').target = value
        return bytes(store), 'text/x-gettext-translation'
    return b'', 'text/plain'


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _answer(self):
        Mock.requests += 1
        body, ctype = good_body(Mock.service, self.path, Mock.value)
        status = 200
        reply = dict((name, (code, data, kind)) for name, code, data, kind in BAD_REPLIES).get(Mock.reply)
        if reply:
            status, data, kind = reply
            if Mock.reply == 'truncated':
                data, kind = body[:len(body) // 2], ctype
            elif Mock.reply == '5 MB':
                data, kind = body + b' ' * 5000000, ctype
            elif Mock.reply == 'slow':
                time.sleep(SLOW_SECONDS)
                data, kind = body, ctype
            body, ctype = data, kind
        try:
            self.send_response(status)
            if status == 302:
                self.send_header('Location', self.path)
            if ctype:
                self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('ETag', '"%d"' % Mock.requests)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_GET = do_POST = do_PUT = _answer


def start_server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return 'http://127.0.0.1:%d' % server.server_address[1]


def _set_option(conf, name, section, key, value):
    import configparser
    path = os.path.join(conf, name)
    parser = configparser.RawConfigParser()
    parser.read(path, encoding='utf-8')
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with open(path, 'w', encoding='utf-8') as f:
        parser.write(f)


def configure(service, url, conf):
    """Turn on only this service, pointed at the mock. Runs before the
    plug-ins read their config."""
    Mock.service = service

    def set_option(name, section, key, value):
        _set_option(conf, name, section, key, value)

    tm_off = {'_dummytm', 'remotetm', 'apertium', 'google_translate', 'moses', 'amagama'}
    model = {'amagama': 'amagama', 'remotetm': 'remotetm', 'apertium': 'apertium', 'moses': 'moses',
             'google': 'google_translate'}.get(service)
    if model:
        tm_off.discard(model)
    set_option('plugins.ini', 'tm', 'disabled_models', ','.join(sorted(tm_off)))
    term_off = {'autoterm', 'pontoon'} - {service}
    set_option('plugins.ini', 'terminology', 'disabled_models', ','.join(sorted(term_off)))
    if service == 'amagama':
        set_option('tm.ini', 'amagama', 'url', url)
    elif service == 'remotetm':
        host, port = url.rsplit('//', 1)[1].split(':')
        set_option('tm.ini', 'remotetm', 'host', host)
        set_option('tm.ini', 'remotetm', 'port', port)
    elif service == 'moses':
        set_option('tm.ini', 'moses', 'en->af', url)
    elif service == 'google':
        set_option('tm.ini', 'google_translate', 'api_key', 'fuzz')


def patch_fixed_urls(service, url):
    """Services whose address is fixed in the code: point them at the mock.
    Runs after Virtaal is imported, before the plug-ins load."""
    if service == 'apertium':
        from virtaal.plugins.tm.models import apertium
        apertium.TMModel.url = url
    elif service == 'google':
        from virtaal.plugins.tm.models import google_translate
        google_translate.TMModel.translate_url = url + '/translate?key=%(key)s&q=%(message)s&source=%(from)s&target=%(to)s'
        google_translate.TMModel.languages_url = url + '/languages?key=%(key)s'
    elif service == 'pontoon':
        from virtaal.plugins.terminology.models import pontoon
        pontoon.TerminologyModel._l10n_URL = url + '/terminology/%(tgtlang)s.tbx'
    elif service == 'autoterm':
        from virtaal.plugins.terminology.models import autoterm
        autoterm.TerminologyModel._l10n_URL = url + '/l10n/%(srclang)s/%(tgtlang)s'


def query_file(workdir, count):
    """A PO file with distinct sources, one per case, so no reply comes
    from a client's cache."""
    from translate.storage import po
    store = po.pofile()
    store.updateheader(add=True, Language='af')
    store.updateheaderplural(2, '(n != 1)')
    for i in range(count):
        store.addsourceunit('Open the fuzz file number %d' % i)
    path = os.path.join(workdir, 'service-queries.po')
    store.savefile(path)
    return path


def check_display(sweep, rec):
    """Every '<', '>' and '&' of each shown suggestion must be shown as text."""
    tm = sweep.mc.plugin_controller.plugins.get('tm')
    if not tm:
        return
    window = tm.controller.view.tmwindow
    for row in window.liststore:
        target = str(row[0].get('target', ''))
        layout = window.match_renderer._get_pango_layout(window.treeview, target, 400, None)
        shown = layout.get_text()
        if any(target.count(c) != shown.count(c) for c in '<>&'):
            rec.problem('display-mismatch', 'suggestion markup', 'suggestion %s shows as %s' % (
                short(target), short(shown)))


def cases():
    out = [(None, 'corpus: ' + name, ('value', value)) for _, name, value in CORPUS]
    out += [(None, 'reply: ' + name, ('reply', name)) for name, _, _, _ in BAD_REPLIES]
    out.append((None, 'close while waiting', ('close', None)))
    return out


def run(sweep, service):
    """The section for one service (a generator, like the other sections)."""
    rec = sweep.rec
    name = 'service-' + service
    if service == 'localtm':
        yield from _run_localtm(sweep, name)
        return
    sc = sweep.mc.store_controller
    path = query_file(sweep.args.workdir, len(cases()) + 2)
    yield from sweep.open_file(path)
    for i, (case, (what, value)) in enumerate(sweep.cases(name, cases()), start=1):
        try:
            Mock.reply = None
            Mock.value = 'Stoor die lêer'
            if what == 'value':
                Mock.value = value
            elif what == 'reply':
                Mock.reply = value
            else:
                Mock.reply = 'slow'
            if service in ('pontoon', 'autoterm'):
                yield from _download(sweep, service)
                continue
            before = Mock.requests
            sc.cursor.force_index(i)
            if what == 'close':
                yield from sweep.settle(30)  # the query is sent, then the file closes
                sc.close_file()
                deadline = time.monotonic() + SLOW_SECONDS + 5
                while time.monotonic() < deadline:
                    yield
                yield from sweep.open_file(path)
                continue
            # Long enough for the query delay and a reply; a slow reply is
            # left running while the sweep moves on.
            for _ in range(75):
                if Mock.requests > before and what != 'reply':
                    break
                yield
            yield from sweep.settle(15)
            if what == 'value':
                check_display(sweep, rec)
        except Exception:
            sweep.failed()


def _download(sweep, service):
    """Fetch the glossary again, as an update does."""
    terminology = sweep.mc.plugin_controller.plugins.get('terminology')
    if not terminology:
        return
    model = terminology.controller.plugin_controller.plugins.get(service)
    if not model:
        sweep.rec.note('%s model not loaded' % service)
        return
    for key in list(model.config):
        if key not in model.default_config:
            del model.config[key]  # forget the ETag so it downloads again
    model._check_for_update('en', 'af')
    deadline = time.monotonic() + (SLOW_SECONDS + 5 if Mock.reply == 'slow' else 5)
    while time.monotonic() < deadline:
        yield
    sweep.mc.store_controller.cursor.force_index(1)
    yield from sweep.settle(15)


def _run_localtm(sweep, name):
    """The local TM full of corpus translations, queried through the TM
    server as the plug-in does."""
    from translate.storage import factory

    from virtaal.common import pan_app
    from virtaal.support.tmdb import TMDB
    path = query_file(sweep.args.workdir, len(CORPUS) + 1)
    store = factory.getobject(path)
    units = [u for u in store.units if not u.isheader()]
    for unit, (_, _, value) in zip(units, CORPUS):
        unit.target = value
    seeded = path.replace('.po', '-tm.po')
    store.savefile(seeded)
    TMDB(os.path.join(pan_app.get_config_dir(), 'tm.db')).add_store(factory.getobject(seeded), 'en', 'af')
    yield from sweep.open_file(path)
    for i, (case, value) in enumerate(sweep.cases(name, [(None, 'corpus: ' + n, v) for _, n, v in CORPUS])):
        try:
            sweep.mc.store_controller.cursor.force_index(i)
            yield from sweep.settle(75)
            check_display(sweep, sweep.rec)
        except Exception:
            sweep.failed()
