#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject

from virtaal.common.gobjectwrapper import GObjectWrapper


class _Widget(GObjectWrapper):
    __gtype_name__ = 'TestGObjectWrapperWidget'
    __gsignals__ = {
        'ping': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'pong': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }


def test_init_enables_every_declared_signal_by_default():
    widget = _Widget()

    assert 'ping' in widget._all_signals
    assert 'pong' in widget._all_signals
    assert widget._enabled_signals == set(widget._all_signals)


def test_emit_fires_an_enabled_signal():
    widget = _Widget()
    received = []
    widget.connect('ping', lambda w: received.append(True))

    widget.emit('ping')

    assert received == [True]


def test_emit_is_silently_swallowed_for_a_disabled_signal():
    widget = _Widget()
    received = []
    widget.connect('ping', lambda w: received.append(True))
    widget.disable_signals(['ping'])

    widget.emit('ping')

    assert received == []


def test_disable_signals_with_no_argument_disables_everything():
    widget = _Widget()
    ping_received = []
    pong_received = []
    widget.connect('ping', lambda w: ping_received.append(True))
    widget.connect('pong', lambda w: pong_received.append(True))

    widget.disable_signals()
    widget.emit('ping')
    widget.emit('pong')

    assert ping_received == []
    assert pong_received == []
    assert widget._enabled_signals == set()


def test_enable_signals_re_enables_only_the_given_signal():
    widget = _Widget()
    widget.disable_signals()

    widget.enable_signals(['ping'])

    assert widget._enabled_signals == {'ping'}


def test_enable_signals_with_no_argument_re_enables_everything():
    widget = _Widget()
    widget.disable_signals()

    widget.enable_signals()

    assert widget._enabled_signals == set(widget._all_signals)
