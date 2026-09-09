#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
