#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Checks the links Virtaal shows - Help menu, tutorial, About, bug
report - and the ones in translator comments (#4662). The metainfo's
are checked by check_metainfo_urls.py. Skipped unless
VIRTAAL_LIVE_SERVICES=1."""

import ast
import concurrent.futures
import os
import re
import sys
import time
from pathlib import Path

import pytest
from translate.storage import pypo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'devsupport' / 'packaging'))
from check_metainfo_urls import check_url, fetch_status  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to check the links online")

URL_RE = re.compile(r'https?://[^\s"<>\')\]]+')
# Not translatable, so not in the POT.
SOURCES = [
    'share/virtaal/virtaal.ui',
    'virtaal/views/widgets/aboutdialog.py',
    'virtaal/support/bug_report.py',
    'virtaal/support/tutorial.py',
]


def _texts(path):
    text = (REPO_ROOT / path).read_text(encoding='utf-8')
    if path.endswith('.py'):
        # Whole strings, with split literals joined.
        return [node.value for node in ast.walk(ast.parse(text))
                if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return [text]


def app_urls():
    """{url: where it was found}"""
    found = {}
    pot = pypo.pofile.parsefile(str(REPO_ROOT / 'po' / 'virtaal.pot'))
    for unit in pot.units:
        for text, kind in ((unit.source, 'message'), (unit.getnotes('developer'), 'translator comment')):
            for url in URL_RE.findall(text or ''):
                found.setdefault(url, 'po/virtaal.pot %s: %s' % (kind, unit.source[:40]))
    for path in SOURCES:
        for text in _texts(path):
            for url in URL_RE.findall(text):
                found.setdefault(url, path)
    return {url.rstrip('.,;:'): where for url, where in found.items()
            if '%' not in url and 'localhost' not in url}


def test_every_link_virtaal_shows_works():
    urls = app_urls()
    assert urls
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        problems = dict(zip(urls, pool.map(lambda u: check_url(u, 'url', fetch_status, time.sleep), urls)))
    for url, problem in problems.items():
        print('%s: %s (%s)' % (problem[0] if problem else 'ok', url, urls[url]))
    errors = ['%s (%s)' % (problem[1], urls[url]) for url, problem in problems.items()
              if problem and problem[0] == 'error']
    assert not errors, '\n'.join(errors)
