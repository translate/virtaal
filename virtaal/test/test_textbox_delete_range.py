#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Characterization tests for TextBox._on_delete_range() - the
placeable-aware Backspace/Delete handler described by its own
in-source truth table (positions a/b/c/d around a placeable
boundary). Written against real GTK buffers/placeable trees (not
fakes) because this code manipulates real Gtk.TextIter objects and
child-anchor widgets; there was no prior test coverage for it at all.
"""

from test_scaffolding import TestScaffolding
from translate.storage import factory

from virtaal.controllers.placeablescontroller import PlaceablesController

PLACEABLES_PO = "devsupport/testfiles/placeables.po"
PLACEABLES_XLIFF = "devsupport/testfiles/placeables.xliff"


def _delete_at(textbox, position, key_is_delete):
    """Simulate the single-character Backspace(at position, deletes
    position-1..position) or Delete(at position, deletes
    position..position+1) a real keypress would fire, then return the
    resulting rendered text."""
    buf = textbox.buffer
    textbox.refresh_cursor_pos = -1
    if key_is_delete:
        start_offset, end_offset = position, position + 1
    else:
        start_offset, end_offset = position - 1, position
    buf.place_cursor(buf.get_iter_at_offset(position))
    buf.delete(buf.get_iter_at_offset(start_offset), buf.get_iter_at_offset(end_offset))
    return textbox.get_text()


class TestTextBoxDeleteRange(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        self.po_store = factory.getobject(PLACEABLES_PO)
        self.xliff_store = factory.getobject(PLACEABLES_XLIFF)

    def _target(self, store, index):
        unit = store.getunits()[index]
        view = self.unit_controller.load_unit(unit)
        # load_unit()/UnitView.load_unit() both no-op when given the
        # same unit object already loaded - force a real re-render so
        # each test starts from a clean, known buffer state.
        view._layout_update_targets()
        return view.targets[0]

    # Newline placeable (PO unit 0, "First line.\nSecond line."):
    # non-editable, fragile, a widget only at its start (idx=11, len=2
    # - the widget plus the literal "\n").

    def test_newline_delete_at_a_removes_the_placeable_and_the_preceding_char(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 11, key_is_delete=True)

        assert result == 'First line\nSecond line.'

    def test_newline_backspace_at_a_only_removes_the_preceding_char(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 11, key_is_delete=False)

        assert result == 'First line\nSecond line.'

    def test_newline_delete_at_b_removes_the_whole_placeable(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 12, key_is_delete=True)

        assert result == 'First line.Second line.'

    def test_newline_backspace_at_b_is_invisible(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 12, key_is_delete=False)

        assert result == 'First line.\nSecond line.'

    def test_newline_delete_at_d_only_removes_the_following_char(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 13, key_is_delete=True)

        assert result == 'First line.\necond line.'

    def test_newline_backspace_at_d_removes_the_whole_placeable(self):
        textbox = self._target(self.po_store, 0)

        result = _delete_at(textbox, 13, key_is_delete=False)

        assert result == 'First line.Second line.'

    # Standalone XLIFF <x/> placeable (XLIFF unit 1, "A line
    # break<x/>after it."): non-editable, fragile, length 1 with only
    # a start widget - position 'd' is unreachable here since it
    # coincides with 'b' in the elif chain (has_start_widget is
    # checked before the plain end-of-length check).

    def test_x_delete_at_a_removes_the_placeable_and_the_preceding_char(self):
        textbox = self._target(self.xliff_store, 1)

        result = _delete_at(textbox, 12, key_is_delete=True)

        assert result == 'A line breaafter it.'

    def test_x_backspace_at_a_only_removes_the_preceding_char(self):
        textbox = self._target(self.xliff_store, 1)

        result = _delete_at(textbox, 12, key_is_delete=False)

        assert result == 'A line breaafter it.'

    def test_x_delete_at_the_b_d_boundary_removes_the_following_char(self):
        textbox = self._target(self.xliff_store, 1)

        result = _delete_at(textbox, 13, key_is_delete=True)

        assert result == 'A line breakfter it.'

    def test_x_backspace_at_the_b_d_boundary_is_invisible(self):
        textbox = self._target(self.xliff_store, 1)

        result = _delete_at(textbox, 13, key_is_delete=False)

        assert result == 'A line breakafter it.'

    # Paired XLIFF <g>here</g> placeable (XLIFF unit 0, "Click
    # <g>here</g> to continue."): editable, widgets at both ends
    # (idx=6, len=6). Positions: a=6, b=7, c=11, d=12.

    def test_g_delete_at_a_removes_the_placeable_and_the_preceding_char(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 6, key_is_delete=True)

        assert result == 'Clickhere to continue.'

    def test_g_backspace_at_a_only_removes_the_preceding_char(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 6, key_is_delete=False)

        assert result == 'Clickhere to continue.'

    def test_g_delete_at_b_deletes_the_first_content_char_normally(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 7, key_is_delete=True)

        assert result == 'Click ere to continue.'

    def test_g_backspace_at_b_is_invisible(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 7, key_is_delete=False)

        assert result == 'Click here to continue.'

    def test_g_delete_at_c_is_invisible(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 11, key_is_delete=True)

        assert result == 'Click here to continue.'

    def test_g_backspace_at_c_deletes_the_last_content_char_normally(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 11, key_is_delete=False)

        assert result == 'Click her to continue.'

    def test_g_delete_at_d_only_removes_the_following_char(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 12, key_is_delete=True)

        assert result == 'Click hereto continue.'

    def test_g_backspace_at_d_removes_the_placeable_and_the_last_content_char(self):
        textbox = self._target(self.xliff_store, 0)

        result = _delete_at(textbox, 12, key_is_delete=False)

        assert result == 'Click her to continue.'

    # Deletions with no placeable boundary involved at all - the
    # ordinary fallback path, unaffected by any of the above.

    def test_multi_char_selection_delete_uses_the_generic_range_path(self):
        textbox = self._target(self.po_store, 4)  # "%s files copied"

        textbox.refresh_cursor_pos = -1
        buf = textbox.buffer
        buf.delete(buf.get_iter_at_offset(3), buf.get_iter_at_offset(9))

        assert textbox.get_text() == '%s copied'

    def test_plain_single_char_delete_far_from_any_placeable(self):
        textbox = self._target(self.po_store, 4)  # "%s files copied"

        textbox.refresh_cursor_pos = -1
        buf = textbox.buffer
        buf.delete(buf.get_iter_at_offset(5), buf.get_iter_at_offset(6))

        assert textbox.get_text() == '%s fies copied'
