#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import ctypes
import ctypes.util
from types import SimpleNamespace

import pytest

from virtaal.common.platform import platform
from virtaal.support.libi18n import locale as locale_module
from virtaal.support.libi18n.locale import (
    _getlang,
    _isofromlangid,
    _putenv,
    bind_libintl_posix,
    fix_libintl,
    fix_locale,
    get_win32_lang,
)


def test_isofromlangid_maps_a_known_langid():
    assert _isofromlangid(1033) == 'en'  # English - United States


def test_isofromlangid_returns_none_for_an_explicitly_unmapped_langid():
    assert _isofromlangid(1083) is None  # Sami (Lappish)


def test_isofromlangid_returns_none_for_an_unknown_langid():
    assert _isofromlangid(999999) is None


def _fake_windll(**kernel32_methods):
    return SimpleNamespace(kernel32=SimpleNamespace(**kernel32_methods))


def test_get_win32_lang_maps_the_users_langid(monkeypatch):
    monkeypatch.setattr(ctypes, 'windll', _fake_windll(GetUserDefaultLangID=lambda: 1033), raising=False)

    assert get_win32_lang() == 'en'


def test_get_win32_lang_uses_the_system_ui_langid_when_requested(monkeypatch):
    monkeypatch.setattr(
        ctypes, 'windll', _fake_windll(GetUserDefaultUILanguage=lambda: 2057), raising=False)

    assert get_win32_lang(system_ui=True) == 'en_GB'


def test_get_win32_lang_defaults_to_c_when_langid_is_zero(monkeypatch):
    monkeypatch.setattr(ctypes, 'windll', _fake_windll(GetUserDefaultLangID=lambda: 0), raising=False)

    assert get_win32_lang() == 'C'


def test_get_win32_lang_defaults_to_c_for_an_unmapped_langid(monkeypatch):
    monkeypatch.setattr(ctypes, 'windll', _fake_windll(GetUserDefaultLangID=lambda: 999999), raising=False)

    assert get_win32_lang() == 'C'


def test_getlang_prefers_the_lang_environment_variable(monkeypatch):
    monkeypatch.setenv('LANG', 'af_ZA.UTF-8')

    assert _getlang() == 'af_ZA.UTF-8'


def test_getlang_falls_back_to_win32_lang_when_unset(monkeypatch):
    monkeypatch.delenv('LANG', raising=False)
    monkeypatch.setattr(locale_module, 'get_win32_lang', lambda: 'fr')

    assert _getlang() == 'fr'


def test_fix_locale_sets_the_language_env_var_when_given_a_lang(monkeypatch):
    monkeypatch.setattr(locale_module.platform, 'is_windows', False)
    monkeypatch.delenv('LANGUAGE', raising=False)

    fix_locale('af')

    assert locale_module.os.environ['LANGUAGE'] == 'af'


def test_fix_locale_does_nothing_without_a_lang_on_posix(monkeypatch):
    monkeypatch.setattr(locale_module.platform, 'is_windows', False)
    monkeypatch.delenv('LANGUAGE', raising=False)

    fix_locale(None)

    assert 'LANGUAGE' not in locale_module.os.environ


def test_fix_locale_on_windows_sets_every_locale_env_var(monkeypatch):
    monkeypatch.setattr(locale_module.platform, 'is_windows', True)
    putenv_calls = []
    monkeypatch.setattr(locale_module, '_putenv', lambda name, value: putenv_calls.append((name, value)))
    for name in ('LANG', 'LC_ALL', 'LANGUAGE'):
        monkeypatch.delenv(name, raising=False)

    fix_locale('af')

    assert putenv_calls == [('LANGUAGE', 'af'), ('LANG', 'af'), ('LC_ALL', 'af')]
    assert locale_module.os.environ['LANG'] == 'af'
    assert locale_module.os.environ['LC_ALL'] == 'af'
    assert locale_module.os.environ['LANGUAGE'] == 'af'


def test_fix_locale_on_windows_falls_back_to_getlang_when_no_lang_given(monkeypatch):
    monkeypatch.setattr(locale_module.platform, 'is_windows', True)
    monkeypatch.setattr(locale_module, '_getlang', lambda: 'fr')
    monkeypatch.setattr(locale_module, '_putenv', lambda name, value: None)
    for name in ('LANG', 'LC_ALL', 'LANGUAGE'):
        monkeypatch.delenv(name, raising=False)

    fix_locale(None)

    assert locale_module.os.environ['LANGUAGE'] == 'fr'


def test_bind_libintl_posix_binds_the_domain():
    bind_libintl_posix('/tmp/some/locale/dir')  # must not raise


def test_bind_libintl_posix_swallows_a_missing_library(monkeypatch):
    monkeypatch.setattr(ctypes.util, 'find_library', lambda name: None)
    monkeypatch.setattr(ctypes, 'CDLL', lambda name: (_ for _ in ()).throw(OSError('no such library')))

    bind_libintl_posix('/tmp/some/locale/dir')  # must not raise


def test_bind_libintl_posix_swallows_a_missing_symbol(monkeypatch):
    monkeypatch.setattr(ctypes, 'CDLL', lambda name: SimpleNamespace())

    bind_libintl_posix('/tmp/some/locale/dir')  # must not raise


@pytest.mark.skipif(not platform.is_windows, reason="_putenv() is Windows-only ctypes plumbing")
def test_putenv_sets_the_real_process_environment_variable():
    # A real WinAPI round trip (not mocked) - this only runs on the
    # test-windows CI job, which is the one place it can mean anything.
    name = 'VIRTAAL_TEST_PUTENV'
    value = 'hello world'

    _putenv(name, value)

    buf = ctypes.create_unicode_buffer(len(value) + 1)
    ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, len(buf))
    assert buf.value == value


@pytest.mark.skipif(not platform.is_windows, reason="fix_libintl() is Windows-only, frozen-build-only ctypes plumbing")
def test_fix_libintl_binds_the_domain_via_the_real_intl_dll(tmp_path):
    # intl.dll ships in C:\gtk\bin (gvsbuild's own gettext.py build
    # recipe) and that directory is on PATH for the whole CI job - a
    # real, unmocked call here fails loudly if that ever stops being
    # true, rather than silently masking it like bind_libintl_posix's
    # own best-effort try/except does for its POSIX equivalent.
    fix_libintl(str(tmp_path))
