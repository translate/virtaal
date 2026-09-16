#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common.signaltracker import SignalTracker


class _FakeObject:
    def __init__(self):
        self._next_id = 1
        self.connected = []
        self.disconnected = []

    def connect(self, signal_name, handler, *args):
        signal_id = self._next_id
        self._next_id += 1
        self.connected.append((signal_name, handler, args))
        return signal_id

    def disconnect(self, signal_id):
        self.disconnected.append(signal_id)


def test_connect_returns_the_real_signal_id():
    obj = _FakeObject()
    tracker = SignalTracker()

    signal_id = tracker.connect(obj, 'activate', lambda: None)

    assert signal_id == 1
    assert obj.connected == [('activate', obj.connected[0][1], ())]


def test_disconnect_all_disconnects_every_tracked_signal():
    obj1, obj2 = _FakeObject(), _FakeObject()
    tracker = SignalTracker()
    id1 = tracker.connect(obj1, 'activate', lambda: None)
    id2 = tracker.connect(obj2, 'clicked', lambda: None)

    tracker.disconnect_all()

    assert obj1.disconnected == [id1]
    assert obj2.disconnected == [id2]


def test_disconnect_all_is_safe_to_call_twice():
    obj = _FakeObject()
    tracker = SignalTracker()
    tracker.connect(obj, 'activate', lambda: None)

    tracker.disconnect_all()
    tracker.disconnect_all()

    assert obj.disconnected == [1]
