#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Downloads terminology from the live Pontoon server through the
plugin's own request and parses it, without loading it into Virtaal
(#4658). Skipped unless VIRTAAL_LIVE_SERVICES=1."""

import os
import random
from pathlib import Path

import pytest
from gi.repository import GLib
from lxml import etree

from virtaal.plugins.terminology.models.pontoon import (
    _TBX_BASIC_NS,
    TerminologyModel,
    _parse_tbx_basic,
)
from virtaal.support.httpclient import HTTPClient

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to query the live Pontoon server")

LINGUAS = Path(__file__).resolve().parents[4] / 'po' / 'LINGUAS'


def _download(tmp_path, tgtlang):
    """Runs the plugin's _check_for_update() for en -> tgtlang. Returns
    (the file it saved or None, the HTTP error status or None, url)."""
    model = TerminologyModel.__new__(TerminologyModel)
    model.TERMDIR = str(tmp_path)
    model.config = {}
    model.matcher = None
    model.source_lang, model.target_lang = 'en', tgtlang
    model.client = HTTPClient()
    model.client.set_virtaal_useragent()
    saved, errors, urls = [], [], []
    loop = GLib.MainLoop()
    # init_matcher() would load the terms into Virtaal; only note the file.
    model.init_matcher = lambda filename='': (saved.append(filename), loop.quit())
    real_get = model.client.get

    def get(url, callback, etag=None, error_callback=None, download=False):
        urls.append(url)
        return real_get(url, callback, etag,
                        error_callback=lambda request, status: (errors.append(status), loop.quit()),
                        download=download)
    model.client.get = get

    model._check_for_update('en', tgtlang)
    GLib.timeout_add_seconds(60, loop.quit)
    loop.run()
    assert saved or errors, 'no reply from %s within 60 s' % urls
    return (saved[0] if saved else None), (errors[0] if errors else None), urls[0]


def test_a_language_pontoon_has_no_terminology_for(tmp_path):
    saved, status, url = _download(tmp_path, 'zz')
    assert status == 404, '%s: expected 404, got %s' % (url, status)
    assert saved is None and not os.listdir(tmp_path)


def test_a_random_shipped_language_downloads_and_parses(tmp_path):
    languages = LINGUAS.read_text(encoding='utf-8').split()
    language = os.environ.get('VIRTAAL_PONTOON_LANGUAGE') or random.choice(languages)
    print('Pontoon terminology for %s (VIRTAAL_PONTOON_LANGUAGE=%s repeats this)' % (language, language))

    saved, status, url = _download(tmp_path, language)
    assert status is None, '%s: HTTP %s' % (url, status)
    content = Path(saved).read_bytes()
    root = etree.fromstring(content)
    assert root.tag == '{%s}tbx' % _TBX_BASIC_NS, '%s: not TBX-Basic (root %s)' % (url, root.tag)
    store = _parse_tbx_basic(content)
    entries = root.findall('.//{%s}conceptEntry' % _TBX_BASIC_NS)
    print('%s: %d concept entries, %d terms parsed' % (url, len(entries), len(store.units)))
    assert len(store.units) <= len(entries)
    if entries:
        assert store.units, '%s: %d concept entries, none parsed' % (url, len(entries))
