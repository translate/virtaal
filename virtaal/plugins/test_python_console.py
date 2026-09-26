#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Characterization tests for PythonConsole's key-press dispatch
(__key_press_event_cb) - previously untested. PythonConsole needs no
Virtaal scaffolding to construct, so these drive it directly with a
minimal fake Gdk.Event."""

import warnings

from gi.repository import Gdk

from virtaal.plugins._python_console import PythonConsole


class _FakeEvent:
    def __init__(self, keyval, state=0):
        self.keyval = keyval
        self._state = state

    def get_state(self):
        return self._state


def _send(console, keyval, state=0):
    # __key_press_event_cb is name-mangled (double leading underscore).
    # Calling it directly, rather than through a real signal emission,
    # means the history Up/Down handlers' stop_emission_by_name() has no
    # live emission to stop and logs a GLib warning - harmless here, but
    # pytest-xdist can't serialize that particular warning class back to
    # the master process (a PyGObject/xdist incompatibility), which
    # crashes the worker. Suppress it rather than let it escape.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return console._PythonConsole__key_press_event_cb(console.view, _FakeEvent(keyval, state))


def _text(console):
    buf = console.view.get_buffer()
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)


def test_ctrl_d_destroys_the_console():
    console = PythonConsole(namespace={})
    destroyed = []
    console.destroy_cb = lambda: destroyed.append(True)

    result = _send(console, Gdk.KEY_d, Gdk.ModifierType.CONTROL_MASK)

    assert destroyed == [True]
    assert result is None


def test_return_evaluates_the_command_and_prints_its_result():
    console = PythonConsole(namespace={})
    console.view.get_buffer().insert(console.view.get_buffer().get_end_iter(), "1 + 1")

    result = _send(console, Gdk.KEY_Return)

    assert result is True
    assert _text(console) == '>>> 1 + 1\n2\n>>> '
    assert console.current_command == ''
    assert console.history == ['1 + 1', '']


def test_return_on_an_unfinished_block_command_stays_in_block_mode():
    console = PythonConsole(namespace={})
    console.view.get_buffer().insert(console.view.get_buffer().get_end_iter(), "if True:")

    result = _send(console, Gdk.KEY_Return)

    assert result is True
    assert console.block_command is True
    assert _text(console) == '>>> if True:\n... '


def test_return_on_a_blank_line_ends_a_block_command_and_runs_it():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.insert(buf.get_end_iter(), "if True:")
    _send(console, Gdk.KEY_Return)
    buf.insert(buf.get_end_iter(), "    pass")
    _send(console, Gdk.KEY_Return)
    assert console.block_command is True  # still open before the blank line

    result = _send(console, Gdk.KEY_Return)

    assert result is True
    assert console.block_command is False
    assert console.current_command == ''
    assert _text(console) == '>>> if True:\n...     pass\n... \n>>> '


def test_ctrl_return_inserts_a_continuation_line_without_running():
    console = PythonConsole(namespace={})
    console.view.get_buffer().insert(console.view.get_buffer().get_end_iter(), "  x = 1")

    result = _send(console, Gdk.KEY_Return, Gdk.ModifierType.CONTROL_MASK)

    assert result is True
    assert console.current_command == '  x = 1\n'
    assert _text(console) == '>>>   x = 1\n...   '  # keeps the previous line's indentation


def test_history_up_and_down_navigate_previous_commands():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.insert(buf.get_end_iter(), "first")
    _send(console, Gdk.KEY_Return)
    buf.insert(buf.get_end_iter(), "second")
    _send(console, Gdk.KEY_Return)

    _send(console, Gdk.KEY_Up)
    assert console.get_command_line() == 'second'

    _send(console, Gdk.KEY_Up)
    assert console.get_command_line() == 'first'

    _send(console, Gdk.KEY_Down)
    assert console.get_command_line() == 'second'


def test_left_at_the_input_mark_blocks_moving_into_the_prompt():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.place_cursor(buf.get_iter_at_mark(buf.get_mark("input")))

    assert _send(console, Gdk.KEY_Left) is True


def test_left_elsewhere_in_the_command_line_is_unblocked():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.insert(buf.get_end_iter(), "abc")
    buf.place_cursor(buf.get_end_iter())

    assert _send(console, Gdk.KEY_Left) is False


def test_home_moves_the_cursor_to_the_input_mark():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.insert(buf.get_end_iter(), "hello")

    result = _send(console, Gdk.KEY_Home)

    assert result is True
    cursor = buf.get_iter_at_mark(buf.get_insert())
    inp = buf.get_iter_at_mark(buf.get_mark("input"))
    assert cursor.equal(inp)


def test_shift_home_selects_back_to_the_input_mark():
    console = PythonConsole(namespace={})
    buf = console.view.get_buffer()
    buf.insert(buf.get_end_iter(), "hello")

    result = _send(console, Gdk.KEY_Home, Gdk.ModifierType.SHIFT_MASK)

    assert result is True
    start, end = buf.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (4, 9)


def test_unhandled_key_falls_through():
    console = PythonConsole(namespace={})

    assert _send(console, Gdk.KEY_a) is None
