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

from virtaal import __version__


def test_version_string_includes_short_commit(monkeypatch):
    monkeypatch.setattr(__version__, 'ver', '1.0.0-beta1')
    monkeypatch.setattr(__version__, 'build_commit', '5bb637f1234567890')
    assert __version__.version_string() == '1.0.0-beta1 (5bb637f)'


def test_version_string_falls_back_when_commit_unknown(monkeypatch):
    monkeypatch.setattr(__version__, 'ver', '1.0.0-beta1')
    monkeypatch.setattr(__version__, 'build_commit', None)
    assert __version__.version_string() == '1.0.0-beta1 (unknown)'
