#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sys

import pytest

from virtaal.common.utils import get_bytes, path_from_file_uri


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
