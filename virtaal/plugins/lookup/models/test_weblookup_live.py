#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Opens every default web look-up's URL, built the way the look-up menu
builds it (#4659). Skipped unless VIRTAAL_LIVE_SERVICES=1."""

import os
import urllib.error
import urllib.request

import pytest

from virtaal.plugins.lookup.models.weblookup import LookupModel

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to open the live look-up sites")

QUERIES = [('translation', 'en', 'af'), ('machine translation', 'en', 'af')]
USER_AGENT = 'virtaal-web-lookup-check'
GONE = (404, 410)


def _menu_urls(urldata, query, srclang, tgtlang):
    """The URL behind each menu item, via create_menu_items() itself."""
    model = LookupModel.__new__(LookupModel)
    model.URLDATA = [dict(urldata, enabled=True)]
    urls = []
    model._on_lookup = lambda item, url: urls.append(url)
    items = model.create_menu_items(query, 'source', srclang, tgtlang, None)
    for item in items:
        item.activate()
    return urls


@pytest.mark.parametrize('urldata', LookupModel.URLDATA, ids=lambda u: u['display_name'])
@pytest.mark.parametrize('query, srclang, tgtlang', QUERIES)
def test_default_look_up_opens_a_page(urldata, query, srclang, tgtlang):
    urls = _menu_urls(urldata, query, srclang, tgtlang)
    assert len(urls) == 1, urls
    request = urllib.request.Request(urls[0], headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
    except urllib.error.HTTPError as e:
        status = e.code
    except (urllib.error.URLError, OSError) as e:
        pytest.fail('%s: %s' % (urls[0], getattr(e, 'reason', e)))
    # A search URL that changed is gone; anything else (a page, or a
    # refusal of an automated request) means the site still serves it.
    assert status not in GONE, '%s: HTTP %s' % (urls[0], status)
    if status >= 400:
        print('warning: %s: HTTP %s (the site refused an automated request)' % (urls[0], status))
