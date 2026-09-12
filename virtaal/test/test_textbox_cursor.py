#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from test_scaffolding import TestScaffolding


class TestTextBoxCursor(TestScaffolding):

    def test_cursor_move_clears_the_pending_refresh_position(self):
        """Accepting an autocomplete suggestion (or any raw
        buffer.insert()) leaves refresh_cursor_pos pointing at the end
        of the inserted text, to be restored on the next refresh(). If
        the user then moves the cursor with no text change (arrow
        keys, Ctrl+Left/Right, a mouse click), that stale target must
        not survive to snap the cursor back on the next refresh() -
        exactly what made typing at the start of a Tab-completed word
        jump the cursor to its end (#3229)."""
        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)
        textbox = view.targets[0]

        textbox.refresh_cursor_pos = 999  # simulates the post-accept state

        textbox._on_event_remove_suggestion()  # what a real cursor move fires

        assert textbox.refresh_cursor_pos == -1
