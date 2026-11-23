#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for AutocorrectDownloader's callback-chain orchestration - a
_FakeClient records each .get() call instead of doing real network
I/O, so the test drives the chain step by step, synchronously."""

import errno
import json

import pytest

from virtaal.common.test_utils import fail_binary_writes
from virtaal.support.autocorrect_downloader import AutocorrectDownloader
from virtaal.support.test_autocorrect_source import (
    AF_ZA_DOCUMENT_LIST,
    CONTENTS_LISTING,
)

LISTING_RESULT = json.dumps(CONTENTS_LISTING).encode('utf-8')


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, error_callback=None, download=False):
        self.calls.append((url, callback, error_callback))

    def last_url(self):
        return self.calls[-1][0]


def test_full_chain_writes_the_file(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append,
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
    downloader = AutocorrectDownloader('xx_YY', on_done=done.append,
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)

    assert done == [False]
    assert list(tmp_path.iterdir()) == []


def test_listing_request_error_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append,
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, _listing_cb, listing_err = client.calls[-1]
    listing_err(None, 500)

    assert done == [False]


def test_document_list_request_error_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append,
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)
    _, _doc_cb, doc_err = client.calls[-1]
    doc_err(None, 404)

    assert done == [False]
    assert list(tmp_path.iterdir()) == []


def test_bad_listing_response_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append,
                                        client=client, target_dir=str(tmp_path))

    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, b'not json')

    assert done == [False]


def test_default_on_done_is_a_noop(tmp_path):
    client = _FakeClient()
    downloader = AutocorrectDownloader('xx_YY', client=client, target_dir=str(tmp_path))
    downloader.start()
    _, listing_cb, _ = client.calls[-1]
    listing_cb(None, LISTING_RESULT)  # no exception


def test_start_with_known_files_skips_discovery(tmp_path):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append,
                                        client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('af-ZA', ['DocumentList.xml'])
    assert client.last_url() == (
        'https://raw.githubusercontent.com/LibreOffice/core/master/'
        'extras/source/autocorr/lang/af-ZA/DocumentList.xml')

    _, doc_cb, _ = client.calls[-1]
    doc_cb(None, AF_ZA_DOCUMENT_LIST)

    assert done == [True]
    assert (tmp_path / 'DocumentList.xml').read_bytes() == AF_ZA_DOCUMENT_LIST


def _fetch_known(tmp_path, target_dir=None):
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append, client=client,
                                        target_dir=target_dir or str(tmp_path))
    downloader.start_with_known_files('af-ZA', ['DocumentList.xml'])
    _, doc_cb, _ = client.calls[-1]
    doc_cb(None, AF_ZA_DOCUMENT_LIST)  # must not raise
    return done


@pytest.mark.parametrize('err', [errno.ENOSPC, errno.EACCES])
def test_write_failure_gives_up_without_a_partial_file(tmp_path, monkeypatch, caplog, err):
    fail_binary_writes(monkeypatch, err)

    done = _fetch_known(tmp_path)

    assert done == [False]
    assert 'Could not save autocorrect data for af_ZA' in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_write_failure_keeps_the_previous_list(tmp_path, monkeypatch):
    (tmp_path / 'DocumentList.xml').write_bytes(b'old list')
    fail_binary_writes(monkeypatch)

    done = _fetch_known(tmp_path)

    assert done == [False]
    assert (tmp_path / 'DocumentList.xml').read_bytes() == b'old list'
    assert [p.name for p in tmp_path.iterdir()] == ['DocumentList.xml']


def test_unwritable_target_folder_gives_up(tmp_path):
    # A file where the folder should be: makedirs() raises.
    (tmp_path / 'af_ZA').write_bytes(b'')

    done = _fetch_known(tmp_path, target_dir=str(tmp_path / 'af_ZA'))

    assert done == [False]


def test_config_folder_error_gives_up(tmp_path, monkeypatch):
    import virtaal.support.autocorrect_downloader as autocorrect_downloader

    def raises(_locale_code):
        raise PermissionError(errno.EACCES, 'injected')
    monkeypatch.setattr(autocorrect_downloader, 'autocorrect_write_dir', raises)
    client = _FakeClient()
    done = []
    downloader = AutocorrectDownloader('af_ZA', on_done=done.append, client=client)
    downloader.start_with_known_files('af-ZA', ['DocumentList.xml'])
    _, doc_cb, _ = client.calls[-1]

    doc_cb(None, AF_ZA_DOCUMENT_LIST)  # must not raise

    assert done == [False]
