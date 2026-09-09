#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Tests for AutocorrectDownloader's callback-chain orchestration - a
_FakeClient records each .get() call instead of doing real network
I/O, so the test drives the chain step by step, synchronously."""

import json

from virtaal.support.autocorrect_downloader import AutocorrectDownloader
from virtaal.support.test_autocorrect_source import (
    AF_ZA_DOCUMENT_LIST,
    CONTENTS_LISTING,
)

LISTING_RESULT = json.dumps(CONTENTS_LISTING).encode('utf-8')


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, error_callback=None):
        self.calls.append((url, callback, error_callback))

    def last_url(self):
        return self.calls[-1][0]


def test_full_chain_writes_the_file(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=lambda: done.append(True),
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    assert client.last_url().endswith('/contents/extras/source/autocorr/lang')

    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)
    assert client.last_url() == (
        'https://raw.githubusercontent.com/LibreOffice/core/master/'
        'extras/source/autocorr/lang/af-ZA/DocumentList.xml')

    _, doc_cb, _ = client.calls[-1]
    doc_cb(None, AF_ZA_DOCUMENT_LIST)

    assert done == [True]
    assert (tmp_path / 'DocumentList.xml').read_bytes() == AF_ZA_DOCUMENT_LIST


def test_no_folder_guess_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('xx_YY', on_done=lambda: done.append(True),
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)

    assert done == [True]
    assert list(tmp_path.iterdir()) == []


def test_listing_request_error_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=lambda: done.append(True),
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, _listing_cb, listing_err = client.calls[-1]
    listing_err(None, 500)

    assert done == [True]


def test_document_list_request_error_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=lambda: done.append(True),
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)
    _, _doc_cb, doc_err = client.calls[-1]
    doc_err(None, 404)

    assert done == [True]
    assert list(tmp_path.iterdir()) == []


def test_bad_listing_response_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=lambda: done.append(True),
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, b'not json')

    assert done == [True]


def test_default_on_done_is_a_noop(tmp_path):
    client = _FakeClient()
    downloader = AutocorrectDownloader('xx_YY', client=client, target_dir=str(tmp_path))
    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)  # no exception
