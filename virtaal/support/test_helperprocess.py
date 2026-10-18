#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sys

from virtaal.common.platform import Platform
from virtaal.support import helperprocess


def test_command_uses_run_module_when_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=True))

    assert helperprocess.command('virtaal.support.x') == [sys.executable, '--run-module', 'virtaal.support.x']


def test_command_uses_module_flag_when_not_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=False))

    assert helperprocess.command('virtaal.support.x') == [sys.executable, '-m', 'virtaal.support.x']


def test_env_adds_pythonpath_when_not_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=False))
    monkeypatch.setattr(helperprocess.os, 'environ', {'PYTHONPATH': '/existing'})

    env = helperprocess.env()

    assert '/existing' in env['PYTHONPATH']
    assert env['PYTHONPATH'] != '/existing'  # something was prepended


def test_env_leaves_pythonpath_untouched_when_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=True))
    monkeypatch.setattr(helperprocess.os, 'environ', {'PYTHONPATH': '/existing'})

    assert helperprocess.env()['PYTHONPATH'] == '/existing'


# host_env(): what the AppImage hands a browser or xdg-open, with the
# variables a real run sets (see build-appimage's smoke test).
_BUNDLE = '/tmp/.mount_VirtaaXYZ'
_APPIMAGE_ENV = {
    'HOME': '/home/u',
    'PATH': '/usr/bin:/bin',
    'APPIMAGE': '/home/u/Virtaal-linux-x86_64.AppImage',
    'LD_LIBRARY_PATH': _BUNDLE,
    'GI_TYPELIB_PATH': _BUNDLE + '/gi_typelibs',
    'GTK_PATH': _BUNDLE,
    'GDK_PIXBUF_MODULE_FILE': '/tmp/tmpgycriwhz',
    'GTK_IM_MODULE_FILE': '/tmp/virtaal-gtk-a5mt647x/immodules.cache',
    'PYENCHANT_LIBRARY_PATH': _BUNDLE + '/enchant/lib/libenchant-2.so.2',
    'XDG_DATA_DIRS': _BUNDLE + '/share:/usr/local/share/:/usr/share/',
    '_PYI_ARCHIVE_FILE': _BUNDLE + '/Virtaal',
}


def test_host_env_drops_the_bundle(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=True))

    assert helperprocess.host_env(_APPIMAGE_ENV, _BUNDLE) == {
        'HOME': '/home/u',
        'PATH': '/usr/bin:/bin',
        'APPIMAGE': '/home/u/Virtaal-linux-x86_64.AppImage',
        'XDG_DATA_DIRS': '/usr/local/share/:/usr/share/',
    }


def test_host_env_restores_what_pyinstaller_replaced(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=True))
    environ = {'LD_LIBRARY_PATH': _BUNDLE + ':/opt/lib', 'LD_LIBRARY_PATH_ORIG': '/opt/lib'}

    assert helperprocess.host_env(environ, _BUNDLE) == {'LD_LIBRARY_PATH': '/opt/lib'}


def test_host_env_keeps_a_similarly_named_directory(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=True))

    assert helperprocess.host_env({'X': _BUNDLE + '2/lib'}, _BUNDLE) == {'X': _BUNDLE + '2/lib'}


def test_host_env_unchanged_when_not_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=False))

    assert helperprocess.host_env(_APPIMAGE_ENV, _BUNDLE) == _APPIMAGE_ENV


def test_host_env_drops_the_appimage_s_own_input_method(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=True))
    environ = {'GTK_IM_MODULE': 'ibus', '_VIRTAAL_SET_GTK_IM_MODULE': '1'}

    assert helperprocess.host_env(environ, _BUNDLE) == {}


def test_host_env_keeps_the_user_s_input_method(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(os_name='posix', sys_platform='linux', frozen=True))

    assert helperprocess.host_env({'GTK_IM_MODULE': 'fcitx'}, _BUNDLE) == {'GTK_IM_MODULE': 'fcitx'}
