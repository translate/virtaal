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

from urllib.parse import parse_qs, urlsplit

from virtaal.common.platform import Platform
from virtaal.support.bug_report import REPO_URL, build_bug_report_url


def _fields(url):
    split = urlsplit(url)
    assert split.geturl().startswith(REPO_URL + "/issues/new?")
    return {k: v[0] for k, v in parse_qs(split.query).items()}


def test_windows_installer():
    plat = Platform(os_name='nt', frozen=True)
    fields = _fields(build_bug_report_url(plat=plat))
    assert fields['template'] == 'bug_report.yml'
    assert fields['os'] == 'Windows'
    assert fields['install-method'] == 'Windows installer'


def test_source_checkout_leaves_install_method_unset():
    # install_method() itself is Platform's own responsibility and
    # tested there (test_platform.py) - this just confirms a None is
    # left out of the URL rather than showing up as "install-
    # method=None".
    plat = Platform(frozen=False, environ={})
    fields = _fields(build_bug_report_url(plat=plat))
    assert 'install-method' not in fields


def test_version_uses_version_string():
    from virtaal import __version__
    fields = _fields(build_bug_report_url(plat=Platform()))
    assert fields['version'] == __version__.version_string()


def test_extra_fields_override_builtin():
    fields = _fields(build_bug_report_url(
        extra_fields={'logs': 'Traceback...', 'os': 'Other'}, plat=Platform()))
    assert fields['logs'] == 'Traceback...'
    assert fields['os'] == 'Other'
