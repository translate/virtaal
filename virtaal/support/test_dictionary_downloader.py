#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for DictionaryDownloader's callback-chain orchestration - a
_FakeClient records each .get() call instead of doing real network
I/O, so the test drives the chain step by step, synchronously."""

import json
import os

from virtaal.support.dictionary_downloader import DictionaryDownloader
from virtaal.support.test_dictionary_source import AR_XCU, DE_XCU

TREE_RESULT = json.dumps({
    'tree': [
        {'path': 'de/dictionaries.xcu'},
        {'path': 'ar/dictionaries.xcu'},
    ],
}).encode('utf-8')


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, error_callback=None):
        self.calls.append((url, callback, error_callback))

    def last_url(self):
        return self.calls[-1][0]


def test_full_chain_writes_both_files(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('de_DE', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    assert client.last_url().endswith('/git/trees/master?recursive=1')

    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    assert client.last_url() == 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/dictionaries.xcu'

    _, xcu_cb, _ = client.calls[-1]
    xcu_cb(None, DE_XCU)
    assert client.last_url().endswith('de_DE_frami.aff')

    _, aff_cb, _ = client.calls[-1]
    aff_cb(None, b'aff content')
    assert client.last_url().endswith('de_DE_frami.dic')

    _, dic_cb, _ = client.calls[-1]
    dic_cb(None, b'dic content')

    assert done == [True]
    assert (tmp_path / 'de_DE_frami.aff').read_bytes() == b'aff content'
    assert (tmp_path / 'de_DE_frami.dic').read_bytes() == b'dic content'


def test_xcu_error_tries_the_next_folder(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('ar_EG', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    # 'ar_EG' has no exact/bare-language candidate folder among
    # {'de', 'ar'} that matches its own prefix ('ar_EG' -> 'ar' is a
    # candidate, but suppose it 404s) - a failure on one folder tries
    # the next rather than giving up outright.
    assert client.last_url().endswith('ar/dictionaries.xcu')
    _, xcu_cb, xcu_err = client.calls[-1]
    xcu_err(None, 404)

    assert client.last_url().endswith('de/dictionaries.xcu')


def test_no_matching_locale_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('xx_YY', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    _, xcu_cb, _ = client.calls[-1]
    xcu_cb(None, DE_XCU)
    _, xcu_cb2, _ = client.calls[-1]
    xcu_cb2(None, AR_XCU)

    assert done == [True]
    assert list(tmp_path.iterdir()) == []


def test_file_error_cleans_up_and_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('de_DE', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    _, xcu_cb, _ = client.calls[-1]
    xcu_cb(None, DE_XCU)

    _, aff_cb, _ = client.calls[-1]
    aff_cb(None, b'aff content')
    assert (tmp_path / 'de_DE_frami.aff').exists()

    _, _dic_cb, dic_err = client.calls[-1]
    dic_err(None, 500)

    assert done == [True]
    assert list(tmp_path.iterdir()) == []


def test_bad_tree_response_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('de_DE', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, b'not json')

    assert done == [True]


def test_tree_request_error_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = DictionaryDownloader('de_DE', on_done=lambda: done.append(True),
                                       client=client, target_dir=str(tmp_path))

    downloader.start()
    _, _tree_cb, tree_err = client.calls[-1]
    tree_err(None, 500)

    assert done == [True]


def test_default_on_done_is_a_noop(tmp_path):
    """on_done is optional - a missing callback must not raise."""
    client = _FakeClient()
    downloader = DictionaryDownloader('xx_YY', client=client, target_dir=str(tmp_path))
    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    _, xcu_cb, _ = client.calls[-1]
    xcu_cb(None, DE_XCU)
    _, xcu_cb2, _ = client.calls[-1]
    xcu_cb2(None, AR_XCU)  # no exception


def test_default_target_dir_is_dictionary_write_dir(monkeypatch):
    import virtaal.support.dictionary_downloader as dictionary_downloader
    monkeypatch.setattr(dictionary_downloader, 'dictionary_write_dir', lambda: '/fake/dir')
    client = _FakeClient()
    downloader = DictionaryDownloader('de_DE', client=client)
    downloader.start()
    _, tree_cb, _ = client.calls[-1]
    tree_cb(None, TREE_RESULT)
    _, xcu_cb, _ = client.calls[-1]
    xcu_cb(None, DE_XCU)
    _, aff_cb, _ = client.calls[-1]

    written = []
    real_open = open

    def fake_open(path, *args, **kwargs):
        written.append(path)
        return real_open(os.devnull, *args, **kwargs)

    monkeypatch.setattr('builtins.open', fake_open)
    monkeypatch.setattr('os.makedirs', lambda *a, **k: None)
    aff_cb(None, b'aff content')

    assert written == [os.path.join('/fake/dir', 'de_DE_frami.aff')]
