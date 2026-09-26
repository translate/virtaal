#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gdk
from test_scaffolding import TestScaffolding
from translate.storage import factory
from translate.storage.placeables.strelem import StringElem

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views.widgets.textbox import colors_equal

PLACEABLES_PO = "devsupport/testfiles/placeables.po"


def test_colors_equal_for_matching_strings():
    assert colors_equal('#ff0000', '#ff0000')


def test_colors_equal_for_different_strings():
    assert not colors_equal('#ff0000', '#00ff00')


def test_colors_equal_for_matching_rgba():
    a = Gdk.RGBA()
    a.parse('#ff0000')
    b = Gdk.RGBA()
    b.parse('#ff0000')
    assert colors_equal(a, b)


def test_colors_equal_mixing_rgba_and_string():
    a = Gdk.RGBA()
    a.parse('#ff0000')
    assert colors_equal(a, '#ff0000')


class TestTextBox(TestScaffolding):
    """Loads real units from devsupport/testfiles/placeables.po through a
    real PlaceablesController, so target/source TextBox widgets get
    genuinely-parsed placeable trees (a PythonFormattingPlaceable for
    %s, not a plain StringElem) - TestScaffolding alone never
    constructs a PlaceablesController, so without this every element
    stays a bare StringElem and placeable selection/navigation always
    no-ops."""

    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        self.placeables_store = factory.getobject(PLACEABLES_PO)

    def _target_for(self, source_text):
        unit = next(u for u in self.placeables_store.getunits() if u.source == source_text)
        # The target textbox is a single widget reused across every test in
        # this class. update_tree() unconditionally re-shows whatever
        # _suggestion currently holds (even across a full unit reload,
        # since hide_suggestion() never clears it) - reset it before
        # load_unit() runs, or a suggestion left behind by an earlier test
        # gets silently re-inserted into this unit's freshly-rendered text.
        for textbox in self.unit_controller.view.targets:
            textbox._suggestion = None
        view = self.unit_controller.load_unit(unit)
        return view.targets[0]

    def test_get_text_returns_the_rendered_placeable_string(self):
        textbox = self._target_for('%s files copied')
        assert textbox.get_text() == '%s files copied'

    def test_get_stringelem_reparses_the_current_text(self):
        textbox = self._target_for('%s files copied')
        reparsed = textbox.get_stringelem()
        assert str(reparsed) == '%s files copied'

    def test_select_elem_selects_a_real_placeable(self):
        textbox = self._target_for('%s files copied')
        placeable = next(
            e for e in textbox.elem.depth_first() if e.__class__ not in textbox.unselectables
        )

        textbox.select_elem(elem=placeable)

        assert textbox.selected_elem is placeable
        assert textbox.selected_elem_index == 0

    def test_select_elem_none_clears_the_current_selection(self):
        textbox = self._target_for('%s files copied')
        placeable = next(
            e for e in textbox.elem.depth_first() if e.__class__ not in textbox.unselectables
        )
        textbox.select_elem(elem=placeable)

        textbox.select_elem(None)

        assert textbox.selected_elem is None
        assert textbox.selected_elem_index is None

    def test_select_elem_ignores_an_element_not_in_this_tree(self):
        textbox = self._target_for('%s files copied')
        foreign = StringElem('unrelated')

        textbox.select_elem(elem=foreign)  # must not raise

        assert textbox.selected_elem is None

    def test_move_elem_selection_selects_via_the_selector_textbox(self):
        textbox = self._target_for('%s files copied')

        textbox.move_elem_selection(1)

        selected = textbox.selector_textbox.selected_elem
        assert selected is not None
        assert str(selected) == '%s'

    def test_suggestion_setter_rejects_an_invalid_dict(self):
        textbox = self._target_for('%s files copied')

        with pytest.raises(ValueError):
            textbox.suggestion = {'missing': 'the required keys'}

    def test_suggestion_show_and_hide_round_trip(self):
        textbox = self._target_for('%d files removed')

        textbox.suggestion = {'text': ' extra', 'offset': len('%d files removed')}

        assert textbox.suggestion_is_visible()
        assert textbox.get_text() == '%d files removed extra'

        textbox.hide_suggestion()

        assert not textbox.suggestion_is_visible()
        assert textbox.get_text() == '%d files removed'

    def test_suggestion_set_to_none_hides_an_existing_one(self):
        textbox = self._target_for('%1 files moved')
        textbox.suggestion = {'text': ' extra', 'offset': len('%1 files moved')}

        textbox.suggestion = None

        assert not textbox.suggestion_is_visible()
        assert textbox.get_text() == '%1 files moved'

    def test_on_event_remove_suggestion_clears_pending_state(self):
        textbox = self._target_for('%(count)s files renamed')
        textbox.suggestion = {'text': ' extra', 'offset': len('%(count)s files renamed')}
        textbox.refresh_cursor_pos = 42

        textbox._on_event_remove_suggestion()

        assert textbox._suggestion is None
        assert textbox.refresh_cursor_pos == -1

    def test_refresh_is_a_noop_when_the_textbox_is_not_visible(self):
        textbox = self._target_for('%s files copied')
        textbox.set_visible(False)
        before = textbox.get_text()
        try:
            textbox.refresh()  # must not raise, and must not touch rendered text

            assert textbox.get_text() == before
        finally:
            # Shared across the whole class - leaving it invisible would
            # silently no-op every later test's refresh().
            textbox.set_visible(True)

    def test_repr_includes_role_and_current_text(self):
        textbox = self._target_for('%s files copied')

        assert repr(textbox) == f'<TextBox {id(textbox):x} target "%s files copied">'
