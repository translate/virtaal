#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gdk
from test_scaffolding import TestScaffolding
from translate.storage import factory
from translate.storage.placeables import general
from translate.storage.placeables.strelem import StringElem

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views.widgets import textbox as textbox_module
from virtaal.views.widgets.textbox import TextBox, colors_equal

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

    def _capture_idle_add(self, monkeypatch):
        # Pumping the real main loop to let GLib.idle_add fire hangs in
        # this suite (issue #3738's leaked windows) - capture and invoke
        # the callback directly instead, per test_localfileview.py.
        calls = []
        monkeypatch.setattr(textbox_module.GLib, 'idle_add', lambda func, *a: calls.append(func))
        return calls

    def test_live_typed_newline_is_recognized_immediately(self, monkeypatch):
        # #3604 regression test. insert_interactive_at_cursor, not the
        # plain insert_at_cursor - matches a real keystroke, and is the
        # only one of the two that exercises begin/end-user-action.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%s files copied')
        textbox.place_cursor(len(textbox.get_text()))

        textbox.buffer.insert_interactive_at_cursor('\n', -1, True)

        assert any(
            isinstance(e, general.NewlinePlaceable) for e in textbox.elem.depth_first()
        )
        assert len(calls) == 1
        calls[0]()

        assert textbox.get_text() == '%s files copied\n'
        # The newline is now rendered as a pilcrow widget plus the real
        # "\n" character, so the buffer's GUI length is one slot longer
        # than the tree text - and the cursor must land at the true end.
        assert textbox.buffer.props.cursor_position == textbox.elem.gui_info.length()

        # Typing right after the pilcrow must not inherit its grey tag.
        textbox.buffer.insert_interactive_at_cursor('d', -1, True)
        d_iter = textbox.buffer.get_iter_at_mark(textbox.buffer.get_insert())
        d_iter.backward_char()
        assert d_iter.get_tags() == []

    def test_live_typed_xml_tag_is_recognized_immediately(self, monkeypatch):
        # Generalizes the #3604 fix beyond newlines: any placeable type
        # recognized at load time must also be recognized live.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%d files removed')
        textbox.place_cursor(len(textbox.get_text()))

        textbox.buffer.insert_interactive_at_cursor('<a>', -1, True)

        assert any(
            isinstance(e, general.XMLTagPlaceable) for e in textbox.elem.depth_first()
        )
        assert len(calls) == 1
        calls[0]()

        assert textbox.get_text() == '%d files removed<a>'

    def test_live_typing_that_matches_no_placeable_is_a_noop(self, monkeypatch):
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%(count)s files renamed')
        textbox.place_cursor(len(textbox.get_text()))
        elem_count_before = len(list(textbox.elem.depth_first()))

        textbox.buffer.insert_interactive_at_cursor('x', -1, True)

        assert textbox.get_text() == '%(count)s files renamedx'
        assert len(list(textbox.elem.depth_first())) == elem_count_before
        assert calls == []

    def test_undo_reverts_a_live_recognized_placeable(self, monkeypatch):
        # Exercises the exact undo_action closure _on_unit_insert_text
        # records (undocontroller.py) rather than going through
        # mnu_undo.activate()'s full _select_unit() path - that path
        # needs a StoreController.cursor that only gets set up by
        # actually opening a file, which TestScaffolding's minimal
        # factory.getobject()+load_unit() setup never does.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%1 files moved')
        self.undo_controller.model.clear()
        original_text = textbox.get_text()
        textbox.place_cursor(len(original_text))

        textbox.buffer.insert_interactive_at_cursor('\n', -1, True)
        assert any(
            isinstance(e, general.NewlinePlaceable) for e in textbox.elem.depth_first()
        )
        assert len(calls) == 1
        calls[0]()

        undo_info = self.undo_controller.model.pop()
        undo_info['action'](undo_info['unit'])
        textbox.refresh(update=True)

        assert not any(
            isinstance(e, general.NewlinePlaceable) for e in textbox.elem.depth_first()
        )
        assert textbox.get_text() == original_text

    def test_insert_translation_groups_a_selection_replace_into_one_undo_step(self):
        textbox = self._target_for('%s files copied')
        self.undo_controller.model.clear()
        original_text = textbox.get_text()
        textbox.buffer.select_range(
            textbox.buffer.get_start_iter(), textbox.buffer.get_end_iter()
        )
        placeable = next(
            e for e in textbox.elem.depth_first() if e.__class__ not in textbox.unselectables
        )

        textbox.insert_translation(placeable)

        assert textbox.get_text() != original_text
        undo_info = self.undo_controller.model.pop()
        assert isinstance(undo_info, list)
        assert len(undo_info) == 2  # the selection-delete and the insert, grouped

        for entry in reversed(undo_info):
            entry['action'](entry['unit'])
        textbox.refresh(update=True)

        assert textbox.get_text() == original_text

    def test_get_stringelem_returns_none_without_an_elem(self):
        textbox = TextBox(self.main_controller)

        assert textbox.get_stringelem() is None

    def test_init_sets_the_initial_text_when_given(self):
        textbox = TextBox(self.main_controller, text='hello')

        assert textbox.get_text() == 'hello'

    def test_get_text_accepts_integer_offsets(self):
        textbox = self._target_for('%s files copied')

        assert textbox.get_text(0, 2) == '%s'

    def test_get_cursor_position_returns_the_buffers_cursor_position(self):
        textbox = self._target_for('%s files copied')
        textbox.place_cursor(3)

        assert textbox.get_cursor_position() == 3

    def test_suggestion_setter_replaces_an_existing_visible_suggestion(self):
        textbox = self._target_for('%d files removed')
        textbox.set_text('%d files removed')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.suggestion = {'text': ' first', 'offset': len('%d files removed')}
        assert textbox.suggestion_is_visible()

        textbox.suggestion = {'text': ' second', 'offset': len('%d files removed')}

        assert textbox.suggestion['text'] == ' second'
        assert textbox.get_text() == '%d files removed second'

    def test_on_key_pressed_tab_accepts_a_visible_suggestion(self, monkeypatch):
        textbox = self._target_for('%d files removed')
        textbox.set_text('%d files removed')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.suggestion = {'text': ' extra', 'offset': len('%d files removed')}
        emitted = []
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: emitted.append((signal, args)))

        result = textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Tab))

        assert result is True
        assert textbox.suggestion is None
        assert textbox.get_text() == '%d files removed extra'
        assert ('changed', ()) in emitted

    def test_on_key_pressed_recognizes_a_special_key_combo(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        emitted = []
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: emitted.append(args) or True)
        event = _FakeKeyEvent(Gdk.KEY_Return, Gdk.ModifierType.CONTROL_MASK)

        result = textbox._on_key_pressed(textbox, event)

        assert result is True
        assert emitted == [(event, 'ctrl-enter')]

    def test_on_key_pressed_passes_through_an_unrecognized_key(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        emitted = []
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: emitted.append(args) or False)
        event = _FakeKeyEvent(Gdk.KEY_a, 0)

        result = textbox._on_key_pressed(textbox, event)

        assert result is False
        assert emitted == [(event, None)]

    def _open_candidates(self, monkeypatch, textbox, candidates=('drank', 'dryf')):
        # Run the deferred show at once, and treat the (never shown) test
        # widget as mapped.
        monkeypatch.setattr(textbox_module.GLib, 'idle_add', lambda func: func())
        monkeypatch.setattr(textbox, 'get_mapped', lambda: True)
        elem = SimpleNamespace(gui_info=SimpleNamespace(
            get_insert_candidates=lambda: list(candidates)))
        textbox.insert_translation(elem)
        return textbox.completion_popup

    def test_insert_translation_with_candidates_opens_the_popup_without_editing(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')
        self.undo_controller.model.clear()

        popup = self._open_candidates(monkeypatch, textbox)

        assert popup.is_showing()
        assert textbox.get_text() == '%s files copied'
        assert self.undo_controller.model.pop() is None
        popup.dismiss()

    def test_accepting_a_candidate_replaces_the_selection_in_one_undo_step(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')
        original_text = textbox.get_text()
        self.undo_controller.model.clear()
        textbox.buffer.select_range(
            textbox.buffer.get_iter_at_offset(3), textbox.buffer.get_iter_at_offset(8))
        popup = self._open_candidates(monkeypatch, textbox)

        popup.move_selection(1)
        result = textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Return))

        assert result is True
        assert not popup.is_showing()
        assert textbox.get_text() == '%s dryf copied'
        undo_info = self.undo_controller.model.pop()
        assert isinstance(undo_info, list)
        assert len(undo_info) == 2  # the selection-delete and the insert, grouped

        for entry in reversed(undo_info):
            entry['action'](entry['unit'])
        textbox.refresh(update=True)

        assert textbox.get_text() == original_text

    def test_enter_on_the_popup_does_not_reach_the_unit_view(self, monkeypatch):
        # Enter is 'go to the next unit' once it reaches the unit view.
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')
        textbox.buffer.place_cursor(textbox.buffer.get_end_iter())
        popup = self._open_candidates(monkeypatch, textbox)
        emitted = []
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: emitted.append(signal))

        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Return))

        assert 'key-pressed' not in emitted
        assert 'changed' in emitted
        assert textbox.get_text() == '%s files copieddrank'

    def test_escape_dismisses_the_popup_leaving_the_text_unchanged(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox)
        emitted = []
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: emitted.append(signal))

        result = textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Escape))

        assert result is True
        assert not popup.is_showing()
        assert emitted == []
        assert textbox.get_text() == '%s files copied'

    def test_arrow_keys_move_the_popup_selection(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox, ('a', 'b', 'c'))

        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Down))
        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Down))
        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Up))

        assert popup.selected_index() == 1
        popup.dismiss()

    def test_a_modifier_key_alone_keeps_the_popup_open(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox)

        result = textbox._on_key_pressed(
            textbox, _FakeKeyEvent(Gdk.KEY_Shift_L, is_modifier=True))

        assert result is True
        assert popup.is_showing()
        popup.dismiss()

    def test_typing_dismisses_the_popup_and_passes_the_key_on(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox)
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: False)

        result = textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_a))

        assert result is False
        assert not popup.is_showing()

    def test_unit_view_signals_when_the_popup_opens_and_closes(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        toggled = []
        handler_id = self.unit_controller.view.connect(
            'completion-popup-toggled', lambda view, showing: toggled.append(showing))
        try:
            popup = self._open_candidates(monkeypatch, textbox)
            popup.dismiss()
        finally:
            self.unit_controller.view.disconnect(handler_id)

        assert toggled == [True, False]

    def test_moving_the_cursor_dismisses_the_popup(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox)

        textbox._on_event_remove_suggestion(textbox)

        assert not popup.is_showing()


class _FakeKeyEvent:
    def __init__(self, keyval, state=0, is_modifier=False):
        self.keyval = keyval
        self._state = state
        self.is_modifier = is_modifier

    def get_state(self):
        return self._state
