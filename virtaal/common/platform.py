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

"""A single, testable place to ask "which platform is this?".

The constructor accepts overrides for testability: reading
``os.name``/``sys.platform`` at call time is untestable on CI, which
only ever runs as one real OS, so tests inject a platform instead of
monkeypatching global state:

    windows = Platform(os_name='nt', sys_platform='win32')
    assert windows.is_windows and not windows.is_mac
"""

import os
import platform as platform_module
import sys


class Platform:
    def __init__(self, os_name=None, sys_platform=None, frozen=None, environ=None, machine=None):
        self.is_windows = (os_name if os_name is not None else os.name) == 'nt'
        self.is_mac = (sys_platform if sys_platform is not None else sys.platform) == 'darwin'
        self.is_linux = not self.is_windows and not self.is_mac
        self.is_frozen = bool(frozen if frozen is not None else getattr(sys, 'frozen', False))
        machine = machine if machine is not None else platform_module.machine()
        self.is_intel = machine == 'x86_64'
        self.is_arm = machine == 'arm64'
        environ = environ if environ is not None else os.environ
        self.is_flatpak = 'FLATPAK_ID' in environ

    def install_method(self):
        """A human-readable label for how this build was installed, or
            None if that can't be told apart (pip install vs. a distro
            package - neither frozen nor Flatpak, nothing left to
            distinguish them by)."""
        if self.is_flatpak:
            return 'Flatpak'
        if self.is_frozen:
            if self.is_windows:
                return 'Windows installer'
            if self.is_mac:
                return 'macOS .dmg'
        return None


platform = Platform()
