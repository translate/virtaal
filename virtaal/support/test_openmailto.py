#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest

from virtaal.common.platform import platform
from virtaal.support import openmailto

# BaseController #

def test_base_controller_open_is_not_implemented():
    controller = openmailto.BaseController('generic')

    with pytest.raises(NotImplementedError):
        controller.open('somefile')


# Controller._invoke() / Controller.open() - real subprocess launching.
# The Windows branch (subprocess.STARTUPINFO()) can't be exercised here -
# that class doesn't exist in the subprocess module at all on non-Windows
# platforms, so there's no way to reach it without a real Windows host. #

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
