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

import os
import platform as platform_module
import sys

from virtaal.common.platform import Platform


def test_windows():
    p = Platform(os_name='nt', sys_platform='win32')
    assert p.is_windows
    assert not p.is_mac
    assert not p.is_linux


def test_mac():
    p = Platform(os_name='posix', sys_platform='darwin')
    assert not p.is_windows
    assert p.is_mac
    assert not p.is_linux


def test_linux():
    p = Platform(os_name='posix', sys_platform='linux')
    assert not p.is_windows
    assert not p.is_mac
    assert p.is_linux


def test_frozen_is_independent_of_os():
    """is_frozen deliberately doesn't fold in is_windows - a frozen
    build exists on any platform and call sites combine the two flags
    themselves where that matters."""
    p = Platform(os_name='posix', sys_platform='darwin', frozen=True)
    assert p.is_mac
    assert p.is_frozen

    p = Platform(os_name='posix', sys_platform='darwin', frozen=False)
    assert not p.is_frozen


def test_defaults_fall_back_to_real_os_and_sys():
    p = Platform()
    assert p.is_windows == (os.name == 'nt')
    assert p.is_mac == (sys.platform == 'darwin')
    assert p.is_frozen == bool(getattr(sys, 'frozen', False))
    assert p.is_intel == (platform_module.machine() == 'x86_64')
    assert p.is_arm == (platform_module.machine() == 'arm64')


def test_intel():
    p = Platform(machine='x86_64')
    assert p.is_intel
    assert not p.is_arm


def test_arm():
    p = Platform(machine='arm64')
    assert not p.is_intel
    assert p.is_arm
