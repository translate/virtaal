#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal import __version__


def test_version_string_includes_short_commit(monkeypatch):
    monkeypatch.setattr(__version__, 'ver', '1.0.0-beta1')
    monkeypatch.setattr(__version__, 'build_commit', '5bb637f1234567890')
    assert __version__.version_string() == '1.0.0-beta1 (5bb637f)'


def test_version_string_falls_back_when_commit_unknown(monkeypatch):
    monkeypatch.setattr(__version__, 'ver', '1.0.0-beta1')
    monkeypatch.setattr(__version__, 'build_commit', None)
    assert __version__.version_string() == '1.0.0-beta1 (unknown)'
