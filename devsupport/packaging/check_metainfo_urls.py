#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Check that every URL in the AppStream metainfo is valid.

Screenshots in this repository are checked in the checkout, since a
PR that renames one still resolves online until it merges. Other URLs
are fetched with retries: a 404 or 410 fails, anything else is only a
warning so an outage can't fail CI. The newest release's URL 404s until
its tag is pushed, so that is a warning too."""

import argparse
import concurrent.futures
import os
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
METAINFO = REPO_ROOT / 'share' / 'metainfo' / 'io.github.translate.Virtaal.metainfo.xml.in'
REPO_RAW_PREFIX = 'https://raw.githubusercontent.com/translate/virtaal/main/'
GONE = (404, 410)
RETRY_DELAYS = (5, 20)
TIMEOUT = 15
USER_AGENT = 'virtaal-metainfo-url-check'


def metainfo_urls(path):
    """(url, kind) for every URL in the metainfo, in file order."""
    root = ET.parse(path).getroot()
    for image in root.iterfind('screenshots/screenshot/image'):
        yield image.text.strip(), 'screenshot'
    for url in root.iterfind('url'):
        yield url.text.strip(), 'url'
    for i, url in enumerate(root.iterfind('releases/release/url')):
        yield url.text.strip(), 'newest release' if i == 0 else 'release'


def fetch_status(url):
    """The final HTTP status of a GET, or the error text if there wasn't one."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError) as e:
        return str(getattr(e, 'reason', e))


def check_url(url, kind, fetch, sleep):
    """None if url is fine, else (level, message), level 'error' or 'warning'."""
    if kind == 'screenshot' and url.startswith(REPO_RAW_PREFIX):
        relpath = url[len(REPO_RAW_PREFIX):]
        if (REPO_ROOT / relpath).is_file():
            return None
        return 'error', '%s: %s is not in the repository' % (url, relpath)

    for delay in RETRY_DELAYS + (None,):
        status = fetch(url)
        if isinstance(status, int) and (status < 400 or status in GONE):
            break
        if delay is not None:
            sleep(delay)
    if isinstance(status, int) and status < 400:
        return None
    if status in GONE and kind != 'newest release':
        return 'error', '%s: HTTP %s' % (url, status)
    if status in GONE:
        return 'warning', '%s: HTTP %s - fine if this release is not tagged yet' % (url, status)
    if isinstance(status, int):
        status = 'HTTP %s' % status
    return 'warning', '%s: %s after %d attempts' % (url, status, len(RETRY_DELAYS) + 1)


def report(level, message):
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print('::%s title=Metainfo URL::%s' % (level, message))
    else:
        print('%s: %s' % (level, message))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('metainfo', nargs='?', default=METAINFO, type=Path)
    args = parser.parse_args()

    urls = list(metainfo_urls(args.metainfo))
    # Concurrently, so retries stay inside the job's timeout.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls) or 1) as pool:
        problems = pool.map(lambda u: check_url(*u, fetch_status, time.sleep), urls)
    errors = 0
    for (url, kind), problem in zip(urls, problems):
        if problem:
            report(*problem)
            errors += problem[0] == 'error'
        else:
            print('ok: %s' % url)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
