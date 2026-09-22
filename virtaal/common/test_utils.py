#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common.utils import get_bytes


def test_get_bytes_encodes_a_str_as_utf8():
    assert get_bytes('café') == 'café'.encode()


def test_get_bytes_returns_bytes_unchanged():
    data = b'\xff\x00raw'

    assert get_bytes(data) is data
