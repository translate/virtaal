#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins
import errno
import os
import stat
import sys

import pytest

from virtaal.common.utils import get_bytes, path_from_file_uri, write_file_atomically


def fail_binary_writes(monkeypatch, err=errno.ENOSPC):
    """Make every file opened 'wb' write half its data, then raise
    OSError(err): a disk that fills up mid-write."""
    real_open = builtins.open

    class _HalfWriter:
        def __init__(self, f):
            self._f = f

        def write(self, data):
            self._f.write(data[:len(data) // 2])
            self._f.flush()
            raise OSError(err, 'injected write failure')

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._f.close()

        def __getattr__(self, name):
            return getattr(self._f, name)

    def fake_open(file, mode='r', *args, **kwargs):
        f = real_open(file, mode, *args, **kwargs)
        if 'w' in mode and 'b' in mode:
            return _HalfWriter(f)
        return f

    monkeypatch.setattr(builtins, 'open', fake_open)


def test_get_bytes_encodes_a_str_as_utf8():
    assert get_bytes('café') == 'café'.encode()


def test_get_bytes_returns_bytes_unchanged():
    data = b'\xff\x00raw'

    assert get_bytes(data) is data


posix_only = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file URIs')
windows_only = pytest.mark.skipif(sys.platform != 'win32', reason='Windows file URIs')


@posix_only
@pytest.mark.parametrize('uri, path', [
    ('file:///home/user/af.po', '/home/user/af.po'),
    ('file:///tmp/50%25%20done.po', '/tmp/50% done.po'),
    ('file:///tmp/%2541.po', '/tmp/%41.po'),
    ('file:///tmp/a%23b.po', '/tmp/a#b.po'),
    ('file:///tmp/%E6%96%87%E4%BB%B6.po', '/tmp/文件.po'),
    ('file://localhost/tmp/af.po', '/tmp/af.po'),
])
def test_path_from_file_uri_decodes_escapes(uri, path):
    assert path_from_file_uri(uri) == path


@posix_only
@pytest.mark.parametrize('uri', ['file:///tmp/50% done.po', 'file://localhost/tmp/50% done.po'])
def test_path_from_file_uri_keeps_an_unescaped_percent(uri):
    assert path_from_file_uri(uri) == '/tmp/50% done.po'


@windows_only
@pytest.mark.parametrize('uri, path', [
    ('file:///C:/translations/af.po', r'C:\translations\af.po'),
    ('file:///C:/tmp/50%25%20done.po', r'C:\tmp\50% done.po'),
])
def test_path_from_file_uri_gives_a_windows_path(uri, path):
    assert path_from_file_uri(uri) == path


def test_write_file_atomically_writes_the_data(tmp_path):
    path = tmp_path / 'list.xml'

    write_file_atomically(str(path), b'new')

    assert path.read_bytes() == b'new'
    assert [p.name for p in tmp_path.iterdir()] == ['list.xml']


def test_write_file_atomically_replaces_an_existing_file(tmp_path):
    path = tmp_path / 'list.xml'
    path.write_bytes(b'old')

    write_file_atomically(str(path), b'new')

    assert path.read_bytes() == b'new'


@pytest.mark.parametrize('err', [errno.ENOSPC, errno.EIO])
def test_write_file_atomically_failure_keeps_the_old_file_and_no_partial_one(tmp_path, monkeypatch, err):
    path = tmp_path / 'list.xml'
    path.write_bytes(b'old')
    fail_binary_writes(monkeypatch, err)

    with pytest.raises(OSError) as raised:
        write_file_atomically(str(path), b'new data')

    assert raised.value.errno == err
    assert path.read_bytes() == b'old'
    assert [p.name for p in tmp_path.iterdir()] == ['list.xml']


def test_write_file_atomically_failure_leaves_nothing_behind(tmp_path, monkeypatch):
    fail_binary_writes(monkeypatch)

    with pytest.raises(OSError):
        write_file_atomically(str(tmp_path / 'list.xml'), b'new data')

    assert list(tmp_path.iterdir()) == []


def test_write_file_atomically_raises_for_a_missing_folder(tmp_path):
    with pytest.raises(OSError):
        write_file_atomically(str(tmp_path / 'missing' / 'list.xml'), b'new')


def test_write_file_atomically_syncs_before_replacing(tmp_path, monkeypatch):
    calls = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, 'fsync', lambda fd: (calls.append('fsync'), real_fsync(fd)))
    monkeypatch.setattr(os, 'replace', lambda a, b: (calls.append('replace'), real_replace(a, b)))

    write_file_atomically(str(tmp_path / 'list.xml'), b'new')

    assert calls == ['fsync', 'replace']


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX file modes')
def test_write_file_atomically_new_file_is_owner_only(tmp_path):
    write_file_atomically(str(tmp_path / 'list.xml'), b'new')

    assert _mode(tmp_path / 'list.xml') == 0o600


@pytest.mark.skipif(os.name == 'nt', reason='POSIX file modes')
def test_write_file_atomically_keeps_an_existing_files_mode(tmp_path):
    path = tmp_path / 'list.xml'
    path.write_bytes(b'old')
    path.chmod(0o640)

    write_file_atomically(str(path), b'new')

    assert path.read_bytes() == b'new'
    assert _mode(path) == 0o640


@pytest.mark.skipif(os.name == 'nt' or os.geteuid() == 0, reason='root can write a read-only file')
def test_write_file_atomically_refuses_a_read_only_file(tmp_path):
    path = tmp_path / 'list.xml'
    path.write_bytes(b'old')
    path.chmod(0o444)

    with pytest.raises(PermissionError):
        write_file_atomically(str(path), b'new')

    assert path.read_bytes() == b'old'
    assert [p.name for p in tmp_path.iterdir()] == ['list.xml']


@pytest.mark.skipif(os.name == 'nt', reason='symlinks need privileges on Windows')
def test_write_file_atomically_updates_a_symlinks_target(tmp_path):
    real = tmp_path / 'real.xml'
    real.write_bytes(b'old')
    link = tmp_path / 'list.xml'
    link.symlink_to(real)

    write_file_atomically(str(link), b'new')

    assert link.is_symlink()
    assert real.read_bytes() == b'new'
