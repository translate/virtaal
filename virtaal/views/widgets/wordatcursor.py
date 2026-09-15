#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk


class WordAtCursorSelector:
    """Selects the word under a right-click when nothing's already
    selected - copy/spell-checker style interactions (Look-up, Add
    Term) shouldn't require dragging out a selection first when a
    plain right-click already says which word is meant.

    Connect a textbox's 'button-press-event' to on_button_press(), then
    call select_word_at_cursor() from that same textbox's
    'populate-popup' handler before checking buf.get_has_selection()."""

    def __init__(self):
        self._pending_click_iter = None

    def on_button_press(self, textbox, event):
        # Only the right-click that's about to open the context menu -
        # capturing every click would leave a stale position behind
        # for a later keyboard-triggered menu (Shift+F10/Menu key)
        # that never involved a click at all.
        if event.button == 3:
            self._pending_click_iter = self._iter_at_event(textbox, event)
        return False

    def select_word_at_cursor(self, buf):
        """Prefers the position on_button_press() just captured over
        the buffer's own insertion-cursor mark: a right-click doesn't
        reliably move that mark first (confirmed live - right-clicking
        anywhere in a never-yet-clicked text box picked the word at
        its very start every time, not the word under the pointer).
        Falls back to the insertion mark for a menu triggered without
        a click at all (e.g. the keyboard Menu key)."""
        cursor = self._pending_click_iter
        self._pending_click_iter = None
        if cursor is None:
            cursor = buf.get_iter_at_mark(buf.get_insert())
        if not cursor.inside_word():
            return
        start = cursor.copy()
        if not start.starts_word():
            start.backward_word_start()
        end = cursor.copy()
        if not end.ends_word():
            end.forward_word_end()
        buf.select_range(start, end)

    def _iter_at_event(self, textbox, event):
        bx, by = textbox.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(event.x), int(event.y))
        found, it = textbox.get_iter_at_location(bx, by)
        return it if found else None
