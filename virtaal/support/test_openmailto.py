#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib
import shutil
import subprocess

import pytest

from virtaal.common.platform import platform
from virtaal.support import openmailto


@pytest.fixture
def reloaded_as():
    """openmailto registers its controllers once, at import time, based
    on platform.is_windows/is_mac - reload it under a forced platform to
    exercise the other branches, then reload it back to the real
    platform before the test ends, whether it passed or raised. Plain
    save/restore rather than monkeypatch, so the final reload always
    runs after the real values are back in place, not before."""
    real_is_windows = platform.is_windows
    real_is_mac = platform.is_mac

    def _reload(is_windows, is_mac):
        platform.is_windows = is_windows
        platform.is_mac = is_mac
        return importlib.reload(openmailto)

    try:
        yield _reload
    finally:
        platform.is_windows = real_is_windows
        platform.is_mac = real_is_mac
        importlib.reload(openmailto)


# BaseController #

def test_base_controller_open_is_not_implemented():
    controller = openmailto.BaseController('generic')

    with pytest.raises(NotImplementedError):
        controller.open('somefile')


# Controller._invoke() / Controller.open() - real subprocess launching #

def test_invoke_uses_windows_startupinfo_and_disables_closefds(monkeypatch):
    # subprocess.STARTUPINFO/STARTF_USESHOWWINDOW don't exist as
    # attributes on non-Windows platforms at all - faked in here rather
    # than skipped, since CI runs a real Windows leg that exercises the
    # unfaked versions of the same code.
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr(platform, 'is_mac', False)

    class FakeStartupInfo:
        def __init__(self):
            self.dwFlags = 0
    monkeypatch.setattr(subprocess, 'STARTUPINFO', FakeStartupInfo, raising=False)
    monkeypatch.setattr(subprocess, 'STARTF_USESHOWWINDOW', 1, raising=False)

    popen_calls = []
    class FakePopen:
        def __init__(self, *args, **kwargs):
            popen_calls.append((args, kwargs))
        def wait(self):
            return 0
    monkeypatch.setattr(subprocess, 'Popen', FakePopen)

    controller = openmailto.Controller('start')
    result = controller._invoke(['start', 'somefile.po'])

    assert result is True
    _args, kwargs = popen_calls[0]
    assert kwargs['close_fds'] is False
    assert kwargs['startupinfo'].dwFlags == 1
    assert kwargs['stdin'] is subprocess.DEVNULL


def test_invoke_returns_true_on_a_successful_command():
    controller = openmailto.Controller('true')

    assert controller._invoke(['true']) is True


def test_invoke_returns_false_on_a_failing_command():
    controller = openmailto.Controller('false')

    assert controller._invoke(['false']) is False


def test_invoke_leaves_stdio_untouched_for_a_tty_program(monkeypatch):
    # Only reachable when nothing (DISPLAY, macOS, Windows) implies a
    # graphical program - a real X11-less Linux console session.
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.setattr(platform, 'is_windows', False)
    monkeypatch.setattr(platform, 'is_mac', False)
    controller = openmailto.Controller('true')

    assert controller._invoke(['true']) is True


def test_invoke_falls_back_to_setpgrp_without_setsid(monkeypatch):
    # Platforms without os.setsid (still POSIX-like, just missing it)
    # fall back to os.setpgrp for the same "own process group" effect.
    monkeypatch.delattr(openmailto.os, 'setsid', raising=False)
    controller = openmailto.Controller('true')

    assert controller._invoke(['true']) is True


def test_open_passes_a_single_filename_through_as_one_argument():
    controller = openmailto.Controller('true')
    invoked = []
    controller._invoke = lambda cmdline: invoked.append(cmdline) or True

    controller.open('somefile.po')

    assert invoked == [['true', 'somefile.po']]


def test_open_passes_a_sequence_of_filenames_through_directly():
    controller = openmailto.Controller('true')
    invoked = []
    controller._invoke = lambda cmdline: invoked.append(cmdline) or True

    controller.open(['a.po', 'b.po'])

    assert invoked == [['true', 'a.po', 'b.po']]


def test_open_returns_false_when_the_program_does_not_exist():
    controller = openmailto.Controller('this-binary-does-not-exist-12345')

    assert controller.open('somefile.po') is False


# open() - module-level dispatcher #

def test_open_delegates_to_the_platforms_registered_controller(monkeypatch):
    calls = []
    monkeypatch.setattr(openmailto, '_open', lambda filename: calls.append(filename) or True)

    result = openmailto.open('somefile.po')

    assert result is True
    assert calls == ['somefile.po']


# _fix_addersses() #

def test_fix_addresses_drops_empty_header_values():
    result = openmailto._fix_addersses(to='', cc=None, subject='Hello')

    assert 'to' not in result
    assert 'cc' not in result
    assert result['subject'] == 'Hello'


def test_fix_addresses_joins_a_sequence_of_recipients():
    result = openmailto._fix_addersses(to=['a@example.com', 'b@example.com'])

    assert result['to'] == 'a@example.com,b@example.com'


def test_fix_addresses_escapes_reserved_mailto_characters():
    # Only the address-like headers (address/to/cc/bcc) go through this
    # escaping - subject/body/attach are left to mailto_format()'s own
    # RFC2231 encoding instead.
    result = openmailto._fix_addersses(to='100% off & free?')

    assert result['to'] == '100%25 off %26 free%3F'


def test_fix_addresses_raises_a_clear_type_error_for_an_unsupported_value():
    with pytest.raises(TypeError, match='string or sequence expected'):
        openmailto._fix_addersses(to=12345)


def test_fix_addresses_leaves_unrelated_kwargs_untouched():
    result = openmailto._fix_addersses(subject='Hello', body='World')

    assert result == {'subject': 'Hello', 'body': 'World'}


# mailto_format() #

def test_mailto_format_builds_a_plain_address_only_uri():
    assert openmailto.mailto_format(address='a@example.com') == 'mailto:a@example.com'


def test_mailto_format_includes_to_cc_bcc_subject_and_body():
    result = openmailto.mailto_format(
        address='a@example.com', to='b@example.com', cc='c@example.com',
        bcc='d@example.com', subject='Hi', body='Hello there')

    assert result.startswith('mailto:a@example.com?')
    assert 'to=b@example.com' in result
    assert 'cc=c@example.com' in result
    assert 'bcc=d@example.com' in result
    assert 'subject=' in result
    assert 'body=' in result


def test_mailto_format_omits_falsy_fields():
    result = openmailto.mailto_format(address='a@example.com', subject='', body=None)

    assert result == 'mailto:a@example.com'


def test_mailto_format_defaults_the_address_to_empty():
    assert openmailto.mailto_format() == 'mailto:'


# mailto() #

def test_mailto_builds_the_uri_and_opens_it(monkeypatch):
    built = []
    monkeypatch.setattr(openmailto, 'mailto_format', lambda **kwargs: built.append(kwargs) or 'mailto:built')
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda uri: opened.append(uri) or True)

    result = openmailto.mailto('a@example.com', subject='Hi')

    assert result is True
    assert opened == ['mailto:built']
    assert built[0]['address'] == 'a@example.com'
    assert built[0]['subject'] == 'Hi'


# Windows branch (module-level Start controller / os.startfile) #

def test_windows_branch_registers_a_start_controller_using_os_startfile(reloaded_as, monkeypatch):
    module = reloaded_as(is_windows=True, is_mac=False)
    called = []
    monkeypatch.setattr(module.os, 'startfile', called.append, raising=False)

    result = module.open('somefile.po')

    assert result is True
    assert called == ['somefile.po']


def test_windows_start_controller_returns_false_when_nothing_handles_the_file(reloaded_as, monkeypatch):
    module = reloaded_as(is_windows=True, is_mac=False)

    def raise_missing(filename):
        raise OSError('No application is associated with the specified file')
    monkeypatch.setattr(module.os, 'startfile', raise_missing, raising=False)

    assert module.open('somefile.po') is False


# Unix branch (module-level KfmClient/detect_desktop_environment/get) #

def test_unix_branch_registers_desktop_controllers_when_display_is_set(reloaded_as, monkeypatch):
    monkeypatch.setenv('DISPLAY', ':0')
    present = {'kfmclient', 'gnome-open'}
    monkeypatch.setattr(shutil, 'which', lambda cmd: ('/usr/bin/' + cmd) if cmd in present else None)

    module = reloaded_as(is_windows=False, is_mac=False)

    assert 'kde-open' in module._controllers
    assert 'gnome-open' in module._controllers
    assert 'exo-open' not in module._controllers
    assert 'xdg-open' not in module._controllers


def test_unix_branch_registers_nothing_without_a_display(reloaded_as, monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)

    module = reloaded_as(is_windows=False, is_mac=False)

    assert module._controllers == {}


def test_detect_desktop_environment_prefers_kde_env_var(reloaded_as, monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.setenv('KDE_FULL_SESSION', 'true')
    module = reloaded_as(is_windows=False, is_mac=False)

    assert module.detect_desktop_environment() == 'kde'


def test_detect_desktop_environment_falls_back_to_gnome_env_var(reloaded_as, monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('KDE_FULL_SESSION', raising=False)
    monkeypatch.setenv('GNOME_DESKTOP_SESSION_ID', '1')
    module = reloaded_as(is_windows=False, is_mac=False)

    assert module.detect_desktop_environment() == 'gnome'


def test_detect_desktop_environment_checks_xprop_for_xfce(reloaded_as, monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('KDE_FULL_SESSION', raising=False)
    monkeypatch.delenv('GNOME_DESKTOP_SESSION_ID', raising=False)
    module = reloaded_as(is_windows=False, is_mac=False)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **kw: ' = "xfce4"')

    assert module.detect_desktop_environment() == 'xfce'


def test_detect_desktop_environment_defaults_to_generic_when_xprop_fails(reloaded_as, monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('KDE_FULL_SESSION', raising=False)
    monkeypatch.delenv('GNOME_DESKTOP_SESSION_ID', raising=False)
    module = reloaded_as(is_windows=False, is_mac=False)

    def raise_missing(*a, **kw):
        raise OSError('no xprop')
    monkeypatch.setattr(module.subprocess, 'check_output', raise_missing)

    assert module.detect_desktop_environment() == 'generic'


def test_get_returns_the_desktop_specific_controller(reloaded_as, monkeypatch):
    module = reloaded_as(is_windows=False, is_mac=False)
    monkeypatch.setattr(module, 'detect_desktop_environment', lambda: 'gnome')
    sentinel = object()
    module._controllers['gnome-open'] = type('FakeController', (), {'open': sentinel})()

    assert module.get() is sentinel


def test_get_falls_back_to_xdg_open_when_the_desktop_specific_controller_is_missing(reloaded_as, monkeypatch):
    module = reloaded_as(is_windows=False, is_mac=False)
    monkeypatch.setattr(module, 'detect_desktop_environment', lambda: 'generic')
    sentinel = object()
    module._controllers.clear()
    module._controllers['xdg-open'] = type('FakeController', (), {'open': sentinel})()

    assert module.get() is sentinel


def test_get_falls_back_to_webbrowser_open_as_a_last_resort(reloaded_as, monkeypatch):
    module = reloaded_as(is_windows=False, is_mac=False)
    monkeypatch.setattr(module, 'detect_desktop_environment', lambda: 'generic')
    module._controllers.clear()

    import webbrowser
    assert module.get() is webbrowser.open
