#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.views.widgets.wordatcursor import WordAtCursorSelector


def test_on_button_press_captures_the_click_position_for_a_right_click():
    selector = WordAtCursorSelector()
    selector._iter_at_event = lambda textbox, event: 'clicked-here'

    selector.on_button_press(None, SimpleNamespace(button=3))

    assert selector._pending_click_iter == 'clicked-here'


def test_on_button_press_ignores_a_left_click():
    # Only the click that's about to open the context menu should be
    # captured - a plain left-click leaving a stale position behind
    # would be wrong for a later keyboard-triggered menu (Shift+F10)
    # that never involved a click at all.
    selector = WordAtCursorSelector()
    selector._iter_at_event = lambda textbox, event: 'clicked-here'

    selector.on_button_press(None, SimpleNamespace(button=1))

    assert selector._pending_click_iter is None


def test_select_word_at_cursor_selects_the_enclosing_word():
    selector = WordAtCursorSelector()
    buf = Gtk.TextBuffer()
    buf.set_text('The quick brown fox')
    buf.place_cursor(buf.get_iter_at_offset(6))  # inside "quick"

    selector.select_word_at_cursor(buf)

    start, end = buf.get_selection_bounds()
    assert buf.get_text(start, end, False) == 'quick'


def test_select_word_at_cursor_does_nothing_on_whitespace():
    selector = WordAtCursorSelector()
    buf = Gtk.TextBuffer()
    buf.set_text('The quick brown fox')
    buf.place_cursor(buf.get_iter_at_offset(3))  # the space after "The"

    selector.select_word_at_cursor(buf)

    assert not buf.get_has_selection()


def test_select_word_at_cursor_prefers_the_captured_click_over_the_insertion_mark():
    # A right-click doesn't reliably move the buffer's own insertion
    # mark first (confirmed live: it kept picking the word at the very
    # start of a never-yet-clicked text box, regardless of where the
    # click actually landed) - the position on_button_press() just
    # captured is used instead.
    selector = WordAtCursorSelector()
    buf = Gtk.TextBuffer()
    buf.set_text('The quick brown fox')
    buf.place_cursor(buf.get_iter_at_offset(0))  # insertion mark stuck at the start
    selector._pending_click_iter = buf.get_iter_at_offset(16)  # actually clicked inside "fox"

    selector.select_word_at_cursor(buf)

    start, end = buf.get_selection_bounds()
    assert buf.get_text(start, end, False) == 'fox'


def test_select_word_at_cursor_consumes_the_captured_click_once():
    selector = WordAtCursorSelector()
    buf = Gtk.TextBuffer()
    buf.set_text('The quick brown fox')
    selector._pending_click_iter = buf.get_iter_at_offset(16)

    selector.select_word_at_cursor(buf)

    assert selector._pending_click_iter is None
