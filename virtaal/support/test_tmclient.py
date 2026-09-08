#!/usr/bin/env python
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

from virtaal.support.tmclient import TMClient


def test_forget_unit_builds_the_url_without_raising():
    """forget_unit()'s URL format string had 2 placeholders but a
    3-value tuple (self.user_agent left in by mistake - it's already
    passed separately as the user_agent= kwarg) - raised TypeError
    immediately on every call, before any network I/O."""
    client = TMClient('http://example.com')
    client.forget_unit('unit source', 'en', 'af')
