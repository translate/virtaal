#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import signal
import socket
import sys
from types import SimpleNamespace

import pytest

from virtaal.common import pan_app
from virtaal.common.platform import Platform
from virtaal.plugins.tm.models import localtm
from virtaal.plugins.tm.models.localtm import TMModel, find_free_port

# localtm.test_port is a production function, not a test - even a
# module-level alias here would make pytest try to collect and run it
# as one, since collection matches on the name "test_port" itself
# regardless of how it's bound. Call it as port_is_free() instead.
port_is_free = localtm.test_port


def test_test_port_true_for_a_free_port():
    # Bind a real socket to get an actually-unused ephemeral port,
    # then immediately free it - it's very unlikely (not proven
    # impossible) to be grabbed by anything else before test_port()
    # gets to it.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()

    assert port_is_free('localhost', port) is True


def test_test_port_false_for_an_occupied_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    try:
        assert port_is_free('localhost', port) is False
    finally:
        s.close()


def test_find_free_port_skips_an_occupied_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    occupied_port = s.getsockname()[1]
    try:
        # A 2-port range containing only the occupied port and its
        # immediate neighbour - narrow enough that a pass here is a
        # real assertion, not a coincidence of a huge random range.
        free_port = find_free_port('localhost', occupied_port, occupied_port + 2)

        assert free_port != occupied_port
        assert port_is_free('localhost', free_port) is True
    finally:
        s.close()


def test_destroy_uses_sigterm_on_posix(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(os_name='posix'))
    killed = []
    monkeypatch.setattr(localtm.os, 'kill', lambda pid, sig: killed.append((pid, sig)))

    model = TMModel.__new__(TMModel)
    model.tmserver = SimpleNamespace(pid=12345)

    model.destroy()

    assert killed == [(12345, signal.SIGTERM)]


def test_destroy_uses_terminateprocess_on_windows(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(os_name='nt'))
    terminated = []

    class _FakeKernel32:
        def TerminateProcess(self, handle, exit_code):
            terminated.append((handle, exit_code))

    class _FakeCtypes(SimpleNamespace):
        windll = SimpleNamespace(kernel32=_FakeKernel32())

    monkeypatch.setitem(sys.modules, 'ctypes', _FakeCtypes())

    model = TMModel.__new__(TMModel)
    model.tmserver = SimpleNamespace(_handle=999)

    model.destroy()

    assert terminated == [(999, -1)]


# _pick_port() #

def _model_with_config(bind='localhost', port=55555, tmdb='/tmp/tm.db'):
    model = TMModel.__new__(TMModel)
    model.config = {'tmserver_bind': bind, 'tmserver_port': port, 'tmdb': tmdb}
    return model


def test_pick_port_uses_the_configured_port_when_free(monkeypatch):
    monkeypatch.setattr(localtm, 'test_port', lambda host, port: True)
    model = _model_with_config(port=55555)

    assert model._pick_port() == 55555


def test_pick_port_falls_back_to_a_free_port_when_the_configured_one_is_taken(monkeypatch):
    monkeypatch.setattr(localtm, 'test_port', lambda host, port: False)
    calls = []
    monkeypatch.setattr(localtm, 'find_free_port', lambda host, lo, hi: calls.append((host, lo, hi)) or 12345)
    model = _model_with_config(bind='localhost', port=55555)

    assert model._pick_port() == 12345
    assert calls == [('localhost', 49152, 65535)]


# _build_tmserver_command() #

def _fake_controller(min_quality=75, max_matches=3):
    return SimpleNamespace(min_quality=min_quality, max_matches=max_matches)


def test_build_tmserver_command_uses_run_module_when_frozen(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=True))
    model = _model_with_config()

    command = model._build_tmserver_command(55555, _fake_controller())

    assert command[:3] == [sys.executable, '--run-module', 'virtaal.support.tmserver']


def test_build_tmserver_command_uses_module_flag_when_not_frozen(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    model = _model_with_config()

    command = model._build_tmserver_command(55555, _fake_controller())

    assert command[:3] == [sys.executable, '-m', 'virtaal.support.tmserver']


def test_build_tmserver_command_includes_bind_port_db_and_controller_settings(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    model = _model_with_config(bind='127.0.0.1', port=55555, tmdb='/tmp/tm.db')

    command = model._build_tmserver_command(55555, _fake_controller(min_quality=80, max_matches=5))

    assert '-b' in command and command[command.index('-b') + 1] == '127.0.0.1'
    assert '-p' in command and command[command.index('-p') + 1] == '55555'
    assert '-d' in command and command[command.index('-d') + 1] == '/tmp/tm.db'
    assert '--min-similarity=80' in command
    assert '--max-candidates=5' in command


def test_build_tmserver_command_appends_debug_flag_when_pan_app_debug(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    monkeypatch.setattr(pan_app, 'DEBUG', True)
    model = _model_with_config()

    command = model._build_tmserver_command(55555, _fake_controller())

    assert command[-1] == '--debug'


def test_build_tmserver_command_omits_debug_flag_by_default(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    monkeypatch.setattr(pan_app, 'DEBUG', False)
    model = _model_with_config()

    command = model._build_tmserver_command(55555, _fake_controller())

    assert '--debug' not in command


# _build_subprocess_env() #

def test_build_subprocess_env_adds_pythonpath_when_not_frozen(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    monkeypatch.setattr(localtm.os, 'environ', {'PYTHONPATH': '/existing'})
    model = _model_with_config()

    env = model._build_subprocess_env()

    assert '/existing' in env['PYTHONPATH']
    assert env['PYTHONPATH'] != '/existing'  # something was prepended


def test_build_subprocess_env_leaves_pythonpath_untouched_when_frozen(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=True))
    monkeypatch.setattr(localtm.os, 'environ', {'PYTHONPATH': '/existing'})
    model = _model_with_config()

    env = model._build_subprocess_env()

    assert env['PYTHONPATH'] == '/existing'


# _launch_tmserver() #

def test_launch_tmserver_starts_the_process_and_builds_a_tmclient(monkeypatch):
    monkeypatch.setattr(localtm, 'platform', Platform(frozen=False))
    model = _model_with_config(bind='localhost', port=55555)
    model._build_subprocess_env = lambda: {'PYTHONPATH': '/x'}
    popen_calls = []

    class _FakePopen:
        def __init__(self, command, env):
            popen_calls.append((command, env))

    monkeypatch.setattr('subprocess.Popen', _FakePopen)
    tmclient_urls = []
    monkeypatch.setattr('virtaal.support.tmclient.TMClient', lambda url: tmclient_urls.append(url) or 'the-client')

    model._launch_tmserver(['the', 'command'], 55555)

    assert popen_calls == [(['the', 'command'], {'PYTHONPATH': '/x'})]
    assert isinstance(model.tmserver, _FakePopen)
    assert tmclient_urls == ['http://localhost:55555/tmserver']
    assert model.tmclient == 'the-client'


def test_launch_tmserver_logs_and_reraises_on_oserror(monkeypatch):
    model = _model_with_config()

    def raise_oserror(command, env):
        raise OSError('boom')
    monkeypatch.setattr('subprocess.Popen', raise_oserror)

    with pytest.raises(OSError):
        model._launch_tmserver(['the', 'command'], 55555)
