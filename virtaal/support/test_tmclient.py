#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.tmclient import TMClient


def test_forget_unit_builds_the_url_without_raising():
    """forget_unit()'s URL format string had 2 placeholders but a
    3-value tuple (self.user_agent left in by mistake - it's already
    passed separately as the user_agent= kwarg) - raised TypeError
    immediately on every call, before any network I/O."""
    client = TMClient('http://example.com')
    client.forget_unit('unit source', 'en', 'af')
