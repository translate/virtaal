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
