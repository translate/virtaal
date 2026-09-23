#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
    assert p.is_flatpak == ('FLATPAK_ID' in os.environ)


def test_bundle_dir_is_the_executables_directory_when_frozen():
    p = Platform(frozen=True, executable='/fake/bundle/virtaal.exe')
    assert p.bundle_dir == '/fake/bundle'


def test_bundle_dir_is_none_when_not_frozen():
    p = Platform(frozen=False, executable='/fake/bundle/virtaal.exe')
    assert p.bundle_dir is None


def test_locale_dir_uses_the_bundle_dir_when_frozen():
    # Real bug this guards against: sys.prefix in a frozen build is the
    # build machine's own Python install prefix, not the bundle - the
    # app's own translations never loaded, in any language, because
    # gettext.translation() (fallback=True) silently found nothing at
    # that wrong path.
    p = Platform(frozen=True, executable='/fake/bundle/virtaal.exe', prefix='/wrong/build/prefix')
    assert p.locale_dir == os.path.join('/fake/bundle', 'share', 'locale')


def test_locale_dir_uses_sys_prefix_when_not_frozen():
    p = Platform(frozen=False, prefix='/fake/venv')
    assert p.locale_dir == os.path.join('/fake/venv', 'share', 'locale')


def test_intel():
    p = Platform(machine='x86_64')
    assert p.is_intel
    assert not p.is_arm


def test_arm():
    p = Platform(machine='arm64')
    assert not p.is_intel
    assert p.is_arm


def test_flatpak():
    p = Platform(environ={'FLATPAK_ID': 'org.translate.Virtaal'})
    assert p.is_flatpak


def test_not_flatpak():
    p = Platform(environ={})
    assert not p.is_flatpak


def test_install_method_windows_installer():
    p = Platform(os_name='nt', sys_platform='win32', frozen=True, environ={})
    assert p.install_method() == 'Windows installer'


def test_install_method_macos_dmg():
    p = Platform(os_name='posix', sys_platform='darwin', frozen=True, environ={})
    assert p.install_method() == 'macOS .dmg'


def test_install_method_flatpak_takes_priority_over_frozen():
    p = Platform(os_name='posix', sys_platform='linux', frozen=True,
                 environ={'FLATPAK_ID': 'org.translate.Virtaal'})
    assert p.install_method() == 'Flatpak'


def test_install_method_unknown_for_a_plain_source_checkout():
    p = Platform(os_name='posix', sys_platform='linux', frozen=False, environ={})
    assert p.install_method() is None
