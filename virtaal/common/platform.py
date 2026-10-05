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
    def __init__(self, os_name=None, sys_platform=None, frozen=None, environ=None, machine=None,
                 executable=None, prefix=None):
        self.is_windows = (os_name if os_name is not None else os.name) == 'nt'
        self.is_mac = (sys_platform if sys_platform is not None else sys.platform) == 'darwin'
        self.is_linux = not self.is_windows and not self.is_mac
        self.is_frozen = bool(frozen if frozen is not None else getattr(sys, 'frozen', False))
        machine = machine if machine is not None else platform_module.machine()
        self.is_intel = machine == 'x86_64'
        self.is_arm = machine == 'arm64'
        environ = environ if environ is not None else os.environ
        self._environ = environ
        self.is_flatpak = 'FLATPAK_ID' in environ
        # A frozen build's sys.prefix is the build machine's own Python
        # install prefix, not the bundle - callers that need the real
        # bundle directory (e.g. to find data files packaged alongside
        # the executable) want this instead. None when not frozen -
        # there's no single bundle directory to speak of.
        executable = executable if executable is not None else sys.executable
        self.bundle_dir = os.path.dirname(executable) if self.is_frozen else None
        # Where a packaged install's compiled translations live -
        # bundle_dir when frozen (see above), sys.prefix otherwise
        # (gettext's own default search path is keyed off
        # sys.base_prefix, missing a venv's own installed translations).
        prefix = prefix if prefix is not None else sys.prefix
        self.locale_dir = os.path.join(self.bundle_dir or prefix, 'share', 'locale')

    def use_app_name_in_title(self):
        """Whether the window title should keep the app-name suffix
            (e.g. "af.po - Virtaal") rather than just the document
            name (translate/virtaal#549).

            True on Windows; on macOS only while unfrozen, since a
            frozen .app already shows "Virtaal" in the Dock/⌘-Tab (an
            unfrozen dev launch shows bare "Python" there)."""
        if self.is_windows:
            return True
        if self.is_mac:
            return not self.is_frozen
        return False

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

    def build_type(self, checkout_dir=None):
        """How this copy of Virtaal was built: 'flatpak', 'frozen' (a
            PyInstaller build), 'source' (a git checkout) or 'installed'
            (pip or a distro package)."""
        if self.is_flatpak:
            return 'flatpak'
        if self.is_frozen:
            return 'frozen'
        if checkout_dir is None:
            checkout_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # .git is a file, not a directory, in a git worktree.
        if os.path.exists(os.path.join(checkout_dir, '.git')):
            return 'source'
        return 'installed'

    def ci_name(self):
        """The CI service this is running under, or None."""
        if self._environ.get('GITHUB_ACTIONS') == 'true':
            return 'github-actions'
        if self._environ.get('CI', '').lower() in ('true', '1'):
            return 'ci'
        return None


platform = Platform()
