#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for ThesaurusDownloader's file-fetch chain - a _FakeClient
records each .get() call instead of doing real network I/O, so the
test drives the chain step by step, synchronously.
on_done(success) - done lists below record the bool passed, not just
that it fired."""

import sys

import pytest

from virtaal.common.test_utils import fail_binary_writes
from virtaal.support.thesaurus_downloader import ThesaurusDownloader


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, callback, error_callback=None, download=False):
        self.calls.append((url, callback, error_callback))

    def last_url(self):
        return self.calls[-1][0]


def test_writes_a_single_dat_file(tmp_path):
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat'])
    assert client.last_url() == (
        'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/'
        'pl/th_pl_PL_v2.dat')

    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')

    assert done == [True]
    assert (tmp_path / 'th_pl_PL_v2.dat').read_bytes() == b'dat content'


def test_ignores_a_non_dat_file_without_fetching_it(tmp_path):
    # A real folder (fr_FR, for one) has no .idx alongside it at all -
    # only the .dat matters, so an .idx entry is dropped up front
    # rather than fetched for nothing.
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('fr_FR', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('fr_FR', ['th_fr_FR_v2.dat', 'th_fr_FR_v2.idx'])
    assert client.last_url().endswith('.dat')

    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')

    assert done == [True]
    assert list(tmp_path.iterdir()) == [tmp_path / 'th_fr_FR_v2.dat']


def test_no_dat_files_gives_up_without_any_request(tmp_path):
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('fr_FR', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('fr_FR', ['th_fr_FR_v2.idx'])

    assert client.calls == []
    assert done == [False]


def test_file_error_cleans_up_and_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('pl', ['a.dat', 'b.dat'])
    _, a_cb, _ = client.calls[-1]
    a_cb(None, b'a content')
    assert (tmp_path / 'a.dat').exists()

    _, _b_cb, b_err = client.calls[-1]
    b_err(None, 500)

    assert done == [False]
    assert list(tmp_path.iterdir()) == []


def test_default_on_done_is_a_noop(tmp_path):
    """on_done is optional - a missing callback must not raise."""
    client = _FakeClient()
    downloader = ThesaurusDownloader('pl_PL', client=client, target_dir=str(tmp_path))
    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat'])
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')  # no exception


def test_write_failure_cleans_up_and_gives_up_instead_of_crashing(tmp_path, monkeypatch):
    import virtaal.support.thesaurus_downloader as thesaurus_downloader

    def raises():
        raise OSError('disk full')
    monkeypatch.setattr(thesaurus_downloader.pan_app, 'get_config_dir', raises)

    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append, client=client)  # no target_dir override

    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat'])
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')

    assert done == [False]


def test_default_target_dir_uses_the_shared_thesaurus_cache_layout(tmp_path, monkeypatch):
    import virtaal.support.thesaurus_downloader as thesaurus_downloader
    monkeypatch.setattr(thesaurus_downloader.pan_app, 'get_config_dir', lambda: str(tmp_path))

    client = _FakeClient()
    downloader = ThesaurusDownloader('pl_PL', client=client)  # no target_dir override

    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat'])
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')

    assert (tmp_path / 'thesaurus' / 'pl_PL' / 'th_pl_PL_v2.dat').read_bytes() == b'dat content'


def test_a_404_tries_the_dictionaries_subfolder(tmp_path):
    # Some packages keep their files in <folder>/dictionaries/ while the
    # manifest lists only the file name (#4656).
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('ca_ES', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('ca', ['th_ca_ES_v3.dat'])
    _, _dat_cb, dat_err = client.calls[-1]
    dat_err(None, 404)
    assert client.last_url().endswith('/ca/dictionaries/th_ca_ES_v3.dat')
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')

    assert done == [True]
    assert (tmp_path / 'th_ca_ES_v3.dat').read_bytes() == b'dat content'


def test_disk_full_leaves_no_partial_file(tmp_path, monkeypatch):
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat'])
    fail_binary_writes(monkeypatch)
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')  # must not raise

    assert done == [False]
    assert list(tmp_path.iterdir()) == []


def test_file_error_after_a_written_file_vanished_still_gives_up(tmp_path):
    client = _FakeClient()
    done = []
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append,
                                      client=client, target_dir=str(tmp_path))

    downloader.start_with_known_files('pl', ['th_pl_PL_v2.dat', 'th_pl_PL_extra.dat'])
    _, dat_cb, _ = client.calls[-1]
    dat_cb(None, b'dat content')
    (tmp_path / 'th_pl_PL_v2.dat').unlink()
    _, _cb, err = client.calls[-1]
    err(None, 500)  # must not raise

    assert done == [False]


@pytest.mark.skipif(sys.platform == 'win32', reason='symlinks need privileges on Windows')
def test_file_error_removes_what_a_symlinked_file_pointed_to(tmp_path):
    client = _FakeClient()
    done = []
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    target = tmp_path / 'thes'
    target.mkdir()
    (elsewhere / 'a.dat').write_bytes(b'old a')
    (target / 'a.dat').symlink_to(elsewhere / 'a.dat')
    downloader = ThesaurusDownloader('pl_PL', on_done=done.append,
                                      client=client, target_dir=str(target))

    downloader.start_with_known_files('pl', ['a.dat', 'b.dat'])
    _, a_cb, _ = client.calls[-1]
    a_cb(None, b'new a')
    _, _b_cb, b_err = client.calls[-1]
    b_err(None, 500)

    assert done == [False]
    assert not (elsewhere / 'a.dat').exists()  # no half-downloaded set left
