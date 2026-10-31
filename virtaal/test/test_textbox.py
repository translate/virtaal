#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from io import BytesIO
from types import SimpleNamespace

import pytest
from gi.repository import Gdk, GObject, Gtk
from test_scaffolding import TestScaffolding
from translate.storage import factory, po, xliff
from translate.storage.placeables import general, parse
from translate.storage.placeables.strelem import StringElem

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views import placeablesguiinfo
from virtaal.views.theme import current_theme
from virtaal.views.widgets import textbox as textbox_module
from virtaal.views.widgets.textbox import (
    TextBox,
    colors_equal,
    unlock_partly_covered_leaves,
)

PLACEABLES_PO = "devsupport/testfiles/placeables.po"
XLIFF_ONE_UNIT = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original="test" source-language="en" target-language="af" datatype="plaintext">
<body><trans-unit id="1"><source>Open</source></trans-unit></body>
</file>
</xliff>
"""
PLURAL_PO = b"""msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "%s file"
msgid_plural "%s files"
msgstr[0] ""
msgstr[1] ""
"""


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


def test_suggestion_css_follows_a_theme_colour_change(monkeypatch):
    loaded = []
    class FakeProvider:
        def load_from_data(self, data):
            loaded.append(data.decode())
    monkeypatch.setattr(textbox_module, '_suggestion_provider', FakeProvider())
    monkeypatch.setattr(textbox_module, '_suggestion_color', None)
    monkeypatch.setitem(textbox_module.current_theme, 'subtle_fg', 'darkgrey')

    textbox_module._ensure_suggestion_css(None)
    textbox_module._ensure_suggestion_css(None)
    monkeypatch.setitem(textbox_module.current_theme, 'subtle_fg', 'grey')
    textbox_module._ensure_suggestion_css(None)

    assert len(loaded) == 2
    assert 'textview.suggestion text selection' in loaded[0]
    assert 'color: darkgrey;' in loaded[0]
    assert 'color: grey;' in loaded[1]


def test_colors_equal_mixing_rgba_and_string():
    a = Gdk.RGBA()
    a.parse('#ff0000')
    assert colors_equal(a, '#ff0000')


def _parsed(text):
    elem = StringElem([parse(StringElem(text), general.parsers)])
    elem.prune()
    return elem


def test_unlock_partly_covered_leaves_lets_delete_range_cut_into_a_placeable():
    elem = _parsed('Oop %s')

    unlock_partly_covered_leaves(elem, 5, 6)
    elem.delete_range(5, 6)

    assert str(elem) == 'Oop %'


def test_unlock_partly_covered_leaves_keeps_a_fully_covered_placeable():
    elem = _parsed('Oop %s')
    placeable = elem.sub[-1]

    unlock_partly_covered_leaves(elem, 3, 6)

    assert elem.sub[-1] is placeable


def test_unlock_partly_covered_leaves_skips_a_placeable_that_is_the_whole_tree():
    # Nothing to replace it in: the root has no parent.
    placeable = _parsed('%s files').flatten()[0]
    assert not placeable.iseditable

    assert not unlock_partly_covered_leaves(placeable, 1, 1)
    assert str(placeable) == '%s'


def test_delete_inside_widget_leaf_deletes_a_range_outside_the_leaf_normally():
    tree = _parsed('ab %s cd')
    placeable = tree.flatten()[1]
    fake_self = SimpleNamespace(elem=tree)

    deleted, _parent, _index = TextBox._delete_inside_widget_leaf(fake_self, placeable, 0, 2)

    assert str(deleted) == 'ab'
    assert str(tree) == ' %s cd'


class _MainController(GObject.Object):
    """Registers controllers one by one, as the real one does at start-up."""
    __gsignals__ = {
        'controller-registered': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }
    placeables_controller = None
    undo_controller = None

    def register(self, name, controller):
        setattr(self, name, controller)
        self.emit('controller-registered', controller)


class _TaggedGUI(placeablesguiinfo.StringElemGUI):
    """GUI info whose tags use the offset forms create_tags() may return."""
    TAGS = {'skipped': None, 'first': (0, -2), 'last': (-2, None), 'clamped': (-10, 1)}

    def create_tags(self):
        tags = []
        for name, span in self.TAGS.items():
            if span is None:
                tags.append((None, None, None))
            else:
                tags.append((Gtk.TextTag(name=name), *span))
        return tags


def _tagged_offsets(textbox, name):
    tag = textbox.buffer.get_tag_table().lookup(name)
    return [i for i in range(textbox.buffer.get_char_count())
            if textbox.buffer.get_iter_at_offset(i).has_tag(tag)]


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

    def test_a_nul_shows_as_a_symbol_and_keeps_the_text_after_it(self):
        # #4349: GTK cut the text short at a NUL.
        textbox = self._target_for('%s files copied')
        try:
            textbox.set_text('a\0b %s')

            assert textbox.get_text() == 'a\u2400b %s'
            assert str(textbox.elem) == 'a\0b %s'
            tag = textbox.buffer.get_tag_table().lookup('nul_symbol')
            assert _tagged_offsets(textbox, 'nul_symbol') == [1]
            dim = Gdk.RGBA()
            dim.parse(current_theme['subtle_fg'])
            assert tag.props.foreground_rgba.equal(dim)
        finally:
            # The text box is shared with the other tests.
            textbox.set_text('%s files copied')

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

    def test_set_text_does_not_accumulate_placeable_tags(self):
        textbox = self._target_for('%s files copied')
        tagtable = textbox.buffer.get_tag_table()
        textbox.set_text('%s files copied')
        size = tagtable.get_size()
        assert size > 0

        for _ in range(5):
            textbox.set_text('%s files copied')

        assert tagtable.get_size() == size

    def test_set_text_keeps_tags_added_by_others(self):
        textbox = self._target_for('%s files copied')
        tagtable = textbox.buffer.get_tag_table()
        other = Gtk.TextTag(name='search_highlight')
        tagtable.add(other)
        try:
            textbox.set_text('%s files copied')

            assert tagtable.lookup('search_highlight') is other
        finally:
            tagtable.remove(other)

    def test_select_elem_does_not_accumulate_placeable_tags(self):
        textbox = self._target_for('%s files copied')
        tagtable = textbox.buffer.get_tag_table()
        count = len(textbox.selectable_elems())
        textbox.select_elem(offset=0)
        size = tagtable.get_size()

        for _ in range(3):
            textbox.select_elem(offset=0)
            # Past the last placeable: clears the selection and re-applies.
            textbox.select_elem(offset=count)
            textbox.select_elem(offset=0)

        assert tagtable.get_size() == size

    def _foreground_at(self, textbox, elem):
        """The foreground of elem's first character, from its top tag."""
        it = textbox.buffer.get_iter_at_offset(textbox.elem.gui_info.index(elem))
        colour = None
        for tag in sorted(it.get_tags(), key=lambda t: t.get_priority()):
            if tag.props.foreground_set:
                colour = tag.props.foreground_rgba
        return colour

    @pytest.fixture
    def textbox(self):
        """The shared target textbox, its text put back afterwards: loading
            the same unit again doesn't re-render it."""
        textbox = self._target_for('%s files copied')
        yield textbox
        textbox.set_text('%s files copied')

    def test_selecting_keeps_every_placeables_own_tags(self, textbox):
        # #4347: re-applying them all for each selection was slow with thousands of placeables.
        textbox.set_text('%s and %d\nand %s')
        textbox.select_elem(offset=0)
        placeable_tags = list(textbox._placeable_tags)

        textbox.select_elem(offset=1)
        textbox.select_elem(offset=2)

        assert textbox._placeable_tags == placeable_tags
        assert textbox._selection_tags

    def test_selection_colours_follow_the_selected_placeable(self, textbox):
        textbox.set_text('%s and %d and %s')
        first, second = textbox.selectable_elems()[:2]
        textbox.select_elem(elem=second)
        unselected = self._foreground_at(textbox, first)

        textbox.select_elem(elem=first)
        selected = self._foreground_at(textbox, first)
        textbox.select_elem(elem=second)

        assert not selected.equal(unselected)
        assert self._foreground_at(textbox, first).equal(unselected)
        assert self._foreground_at(textbox, second).equal(selected)

    def test_set_text_adds_widgets_after_tagging(self, textbox):
        # #4347: with a pilcrow widget per newline in the view, each tag cost time per widget.
        widgets_when_tagged = []
        apply_all = textbox._apply_all_tags

        def record():
            widgets_when_tagged.append(len(textbox.get_children()))
            apply_all()
        textbox._apply_all_tags = record
        try:
            textbox.set_text('one\ntwo\nthree')
        finally:
            del textbox._apply_all_tags

        assert widgets_when_tagged == [0]
        assert len(textbox.get_children()) >= 2
        assert textbox._deferred_children is None

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

    def test_plain_keystroke_does_not_rebuild_the_buffer(self, monkeypatch):
        # #2020: a full refresh()/set_text() rebuild on every keystroke is
        # what resets the scrollbar on a long unit. A plain character (no
        # placeable/structure change) is already applied natively by GTK,
        # so end-user-action must only reposition the cursor, not rebuild.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%(count)s files renamed')
        textbox.set_text('%(count)s files renamed')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.place_cursor(len(textbox.get_text()))
        refresh_calls = []
        monkeypatch.setattr(textbox, 'refresh', lambda *a, **kw: refresh_calls.append(1))

        textbox.buffer.insert_interactive_at_cursor('x', -1, True)

        assert calls == []
        assert refresh_calls == []
        assert textbox.get_text() == '%(count)s files renamedx'
        assert textbox.buffer.props.cursor_position == len('%(count)s files renamedx')

    def test_place_cursor_scrolls_once_line_heights_are_known(self, monkeypatch):
        # #4151: after a newline rebuilds the buffer, scroll_to_iter() used
        # estimated line heights and left the cursor off screen by a
        # different amount on each press. The insert mark is scrolled to
        # only once the lines are measured.
        textbox = self._target_for('%(count)s files renamed')
        textbox.set_text('%(count)s files renamed')
        scrolled = []
        monkeypatch.setattr(textbox, 'scroll_to_iter', lambda *a: pytest.fail('scroll_to_iter'))
        monkeypatch.setattr(textbox, 'scroll_mark_onscreen', scrolled.append)

        textbox.place_cursor(3)

        assert scrolled == [textbox.buffer.get_insert()]
        assert textbox.buffer.props.cursor_position == 3

    def test_plain_keystroke_still_emits_changed(self, monkeypatch):
        # set_text() is the only other place that emits 'changed' - the
        # unit-level listener that commits the edit into unit.target relies
        # on it. Skipping refresh() for a plain keystroke must not also
        # skip that emission, or the edit never reaches the underlying unit
        # (looks right on screen, vanishes on navigating away and back).
        self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%(count)s files renamed')
        textbox.set_text('%(count)s files renamed')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.place_cursor(len(textbox.get_text()))
        changed_calls = []
        textbox.connect('changed', lambda *a: changed_calls.append(1))

        textbox.buffer.insert_interactive_at_cursor('x', -1, True)

        assert changed_calls == [1]

    def test_structural_keystroke_still_rebuilds_the_buffer(self, monkeypatch):
        # Typing a placeable-forming character (e.g. a newline) still needs
        # the real rebuild, since gui_info/widgets genuinely changed.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.place_cursor(len(textbox.get_text()))
        refresh_calls = []
        monkeypatch.setattr(textbox, 'refresh', lambda *a, **kw: refresh_calls.append(1))

        textbox.buffer.insert_interactive_at_cursor('\n', -1, True)

        assert refresh_calls == []  # deferred: rebuilding inside insert-text crashes gtkspell
        assert len(calls) == 1
        calls[0]()
        assert refresh_calls == [1]

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

    def test_undo_removes_a_typed_placeable_one_keystroke_at_a_time(self, monkeypatch):
        # #4167: typing "s" turns the "%s" just typed into a non-editable
        # placeable, which each keystroke's undo must still be able to cut.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%s files copied')
        original_text = textbox.get_text()
        textbox.set_text('')
        self.undo_controller.model.clear()
        texts = []
        try:
            for char in 'Oop %s':
                textbox.buffer.insert_interactive_at_cursor(char, -1, True)
                for call in calls:
                    call()
                calls.clear()
            assert any(
                isinstance(e, general.PythonFormattingPlaceable) for e in textbox.elem.depth_first()
            )

            while (undo_info := self.undo_controller.model.pop()) is not None:
                undo_info['action'](undo_info['unit'])
                textbox.refresh(update=True)
                texts.append(textbox.get_text())
        finally:
            textbox.set_text(original_text)

        assert texts == ['Oop %', 'Oop ', 'Oop', 'Oo', 'O', '']

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

    def test_undo_restores_deleted_newlines_where_they_were(self, monkeypatch):
        # #4176: typing builds nested elements, so a deleted newline's
        # parent need not start at offset 0.
        calls = self._capture_idle_add(monkeypatch)
        textbox = self._target_for('%s files copied')
        original_text = textbox.get_text()
        textbox.set_text('Maak')
        textbox.place_cursor(len('Maak'))
        self.undo_controller.model.clear()

        def run_idle():
            for call in calls:
                call()
            calls.clear()

        texts = []
        try:
            for char in '\nxx\nyy\n':
                textbox.buffer.insert_interactive_at_cursor(char, -1, True)
                run_idle()
            assert str(textbox.elem) == 'Maak\nxx\nyy\n'
            for _ in range(7):
                cursor = textbox.buffer.get_iter_at_mark(textbox.buffer.get_insert())
                textbox.buffer.backspace(cursor, True, True)
                run_idle()
            assert str(textbox.elem) == 'Maak'

            for _ in range(7):
                undo_info = self.undo_controller.model.pop()
                undo_info['action'](undo_info['unit'])
                textbox.refresh(update=True)
                texts.append(str(textbox.elem))
        finally:
            textbox.set_text(original_text)

        assert texts == [
            'Maak\n', 'Maak\nx', 'Maak\nxx', 'Maak\nxx\n',
            'Maak\nxx\ny', 'Maak\nxx\nyy', 'Maak\nxx\nyy\n',
        ]

    def test_loading_a_unit_selects_its_first_placeable(self):
        # So that Alt+Down inserts it without Alt+Right first (#3963).
        target = self._target_for('Click <a>here</a> to continue.')
        source = target.selector_textbox

        assert source.selected_elem is source.selectable_elems()[0]

    def test_placeable_selection_stops_at_the_last_and_first_placeable(self):
        target = self._target_for('Click <a>here</a> to continue.')
        source = target.selector_textbox
        elems = source.selectable_elems()
        assert len(elems) >= 2

        target.move_elem_selection(len(elems) + 3)
        assert source.selected_elem is elems[-1]
        target.move_elem_selection(1)
        assert source.selected_elem is elems[-1]

        target.move_elem_selection(-(len(elems) + 3))
        assert source.selected_elem is elems[0]
        target.move_elem_selection(-1)
        assert source.selected_elem is elems[0]

    def test_select_first_elem_replaces_a_stale_selection(self):
        # A terminology rescan re-parses the source, replacing the placeables.
        target = self._target_for('Click <a>here</a> to continue.')
        source = target.selector_textbox
        source.select_elem(elem=source.selectable_elems()[1])
        source.selected_elem = StringElem('gone')

        source.select_first_elem()

        assert source.selected_elem is source.selectable_elems()[0]

    def test_select_first_elem_ignores_text_without_placeable_gui_info(self):
        # Without a PlaceablesController the text never gets gui_info; a
        # unit load still calls this, and must not fail.
        textbox = TextBox(self.main_controller)
        textbox.elem = StringElem([StringElem('%s'), StringElem(' files')])

        textbox.select_first_elem()

        assert textbox.selected_elem is None

    def test_init_leaves_insert_emoji_out_of_the_context_menu(self):
        textbox = TextBox(self.main_controller)

        assert textbox.get_input_hints() & Gtk.InputHints.NO_EMOJI

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

    def test_suggestion_is_styled_apart_from_a_real_selection(self):
        textbox = self._target_for('%d files removed')
        textbox.set_text('%d files removed')  # reset - an earlier test in this shared-widget class may have mutated it
        style = textbox.get_style_context()

        textbox.suggestion = {'text': ' extra', 'offset': len('%d files removed')}
        assert style.has_class('suggestion')

        textbox.suggestion = None
        assert not style.has_class('suggestion')

    def test_accepting_a_suggestion_drops_its_style(self, monkeypatch):
        textbox = self._target_for('%d files removed')
        textbox.set_text('%d files removed')  # reset - an earlier test in this shared-widget class may have mutated it
        textbox.suggestion = {'text': ' extra', 'offset': len('%d files removed')}
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: None)

        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Tab))

        assert not textbox.get_style_context().has_class('suggestion')

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

    def test_accepting_a_candidate_moves_the_placeable_selection_on(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        moved = []
        monkeypatch.setattr(textbox, 'move_elem_selection', moved.append)
        popup = self._open_candidates(monkeypatch, textbox)

        assert moved == []
        popup.accept()

        assert moved == [1]

    def test_dismissing_the_popup_keeps_the_placeable_selection(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        moved = []
        monkeypatch.setattr(textbox, 'move_elem_selection', moved.append)
        popup = self._open_candidates(monkeypatch, textbox)

        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_Escape))

        assert moved == []

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
            'editor-popup-toggled', lambda view, showing: toggled.append(showing))
        try:
            popup = self._open_candidates(monkeypatch, textbox)
            popup.dismiss()
        finally:
            self.unit_controller.view.disconnect(handler_id)

        assert toggled == [True, False]

    def test_unit_view_signals_when_a_context_menu_opens_and_closes(self):
        textbox = self._target_for('%s files copied')
        toggled = []
        handler_id = self.unit_controller.view.connect(
            'editor-popup-toggled', lambda view, showing: toggled.append(showing))
        try:
            menu = Gtk.Menu()
            textbox.emit('populate-popup', menu)
            menu.show()
            menu.hide()
        finally:
            self.unit_controller.view.disconnect(handler_id)

        assert toggled == [True, False]

    def test_moving_the_cursor_dismisses_the_popup(self, monkeypatch):
        textbox = self._target_for('%s files copied')
        popup = self._open_candidates(monkeypatch, textbox)

        textbox._on_event_remove_suggestion(textbox)

        assert not popup.is_showing()


    def _xliff_target(self):
        """The target text box for a fresh, untranslated XLIFF unit."""
        self.xliff_store = xliff.xlifffile.parsestring(XLIFF_ONE_UNIT)
        unit = self.xliff_store.units[0]
        for textbox in self.unit_controller.view.targets:
            textbox._suggestion = None
        return unit, self.unit_controller.load_unit(unit).targets[0]

    def test_control_characters_typed_into_an_xliff_target_are_dropped(self):
        # #4330: XML can't hold control characters such as U+000B; the
        # error on every change used to lose the target.
        unit, textbox = self._xliff_target()

        textbox.buffer.insert_interactive_at_cursor('a\x0bb\x0c', -1, True)

        assert textbox.get_text() == 'ab'
        assert unit.target == 'ab'
        assert textbox.buffer.props.cursor_position == 2

    def test_a_lone_control_character_leaves_an_xliff_target_unchanged(self):
        unit, textbox = self._xliff_target()
        textbox.buffer.insert_interactive_at_cursor('a', -1, True)

        textbox.buffer.insert_interactive_at_cursor('\x0b', -1, True)

        assert textbox.get_text() == 'a'
        assert unit.target == 'a'

    def test_undo_removes_a_paste_whose_control_characters_were_dropped(self):
        unit, textbox = self._xliff_target()
        textbox.buffer.insert_interactive_at_cursor('x', -1, True)
        self.undo_controller.model.clear()

        textbox.buffer.insert_interactive_at_cursor('a\x0bb', -1, True)
        undo_info = self.undo_controller.model.pop()
        for entry in reversed(undo_info if isinstance(undo_info, list) else [undo_info]):
            entry['action'](entry['unit'])
        textbox.refresh(update=True)

        assert textbox.get_text() == 'x'
        assert unit.target == 'x'

    def test_set_text_drops_control_characters_from_an_xliff_target(self):
        unit, textbox = self._xliff_target()

        textbox.set_text('a\x0bb')

        assert textbox.get_text() == 'ab'
        assert unit.target == 'ab'

    def test_po_targets_keep_control_characters(self):
        textbox = self._target_for('%s files copied')
        textbox.place_cursor(len(textbox.get_text()))

        textbox.buffer.insert_interactive_at_cursor('\x0b', -1, True)

        assert textbox.get_text().endswith('\x0b')

    def test_show_suggestion_given_a_suggestion_inserts_it_once(self):
        textbox = TextBox(self.main_controller, text='abc')

        textbox.show_suggestion({'text': 'XY', 'offset': 3})

        assert textbox.get_text() == 'abcXY'
        assert textbox.suggestion_is_visible()

    def test_typing_while_a_suggestion_shows_drops_it(self, monkeypatch):
        textbox = TextBox(self.main_controller, text='abc')
        textbox.suggestion = {'text': 'XY', 'offset': 3}
        monkeypatch.setattr(textbox, 'emit', lambda signal, *args: False)

        textbox._on_key_pressed(textbox, _FakeKeyEvent(Gdk.KEY_a))

        assert textbox.suggestion is None
        assert textbox.get_text() == 'abc'

    def test_select_elem_rejects_both_an_elem_and_an_offset(self):
        textbox = TextBox(self.main_controller, text='%s files')

        with pytest.raises(ValueError):
            textbox.select_elem(elem=textbox.selectable_elems()[0], offset=0)

    def test_select_elem_by_offset_without_placeables_selects_nothing(self):
        textbox = TextBox(self.main_controller, text='no placeables')

        textbox.select_elem(offset=0)

        assert textbox.selected_elem is None

    def test_select_elem_colours_a_placeable_that_has_no_gui_info(self):
        textbox = TextBox(self.main_controller, text='%s files')
        placeable = textbox.selectable_elems()[0]
        del placeable.gui_info

        textbox.select_elem(elem=placeable)

        assert textbox.selected_elem is placeable
        assert placeable.gui_info.fg == current_theme['selected_placeable_fg']
        assert placeable.gui_info.bg == current_theme['selected_placeable_bg']

    def test_selectable_elems_is_empty_without_text(self):
        assert TextBox(self.main_controller).selectable_elems() == []

    def test_move_elem_selection_without_placeables_selects_nothing(self):
        textbox = TextBox(self.main_controller, text='no placeables')

        textbox.move_elem_selection(1)

        assert textbox.selected_elem is None

    def test_move_elem_selection_back_from_no_selection_selects_the_last_placeable(self):
        target = self._target_for('Click <a>here</a> to continue.')
        source = target.selector_textbox
        source.select_elem(None)

        target.move_elem_selection(-1)

        assert source.selected_elem is source.selectable_elems()[-1]

    def test_move_elem_selection_highlights_only_the_selecting_plural_source(self, monkeypatch):
        # Not the open store, so its plural count comes from the language.
        monkeypatch.setattr(self.lang_controller, 'get_target_nplurals', lambda: 2)
        view = self.unit_controller.load_unit(po.pofile(BytesIO(PLURAL_PO)).units[1])
        target = view.targets[0]
        assert len(target.selector_textboxes) == 2

        target.move_elem_selection(1)

        def css(source):
            return source.get_parent()._selector_fg_provider.to_string()
        selector, other = target.selector_textbox, target.selector_textboxes[1]
        assert selector is target.selector_textboxes[0]
        expected = Gtk.CssProvider()
        expected.load_from_data(('* { color: %s; }' % target.selector_color).encode())
        assert css(selector) == expected.to_string()
        assert css(other) != css(selector)

    def test_refresh_without_an_elem_parses_the_shown_text(self):
        textbox = TextBox(self.main_controller, text='%s files')
        textbox.set_visible(True)
        textbox.elem = None

        textbox.refresh()

        assert str(textbox.elem) == '%s files'
        assert [str(e) for e in textbox.selectable_elems()] == ['%s']

    def test_update_tree_without_an_elem_renders_an_empty_one(self):
        textbox = TextBox(self.main_controller)

        textbox.update_tree()

        assert str(textbox.elem) == ''
        assert textbox.elem.gui_info is not None

    def test_apply_gui_info_places_tags_relative_to_the_placeable(self):
        # The placeable is "%s", at 3-5; a negative offset counts from its end.
        textbox = TextBox(self.main_controller, text='ab %s cd')
        placeable = textbox.selectable_elems()[0]
        placeable.gui_info = _TaggedGUI(elem=placeable, textbox=textbox)

        textbox.apply_gui_info(placeable, include_subtree=False)

        assert _tagged_offsets(textbox, 'first') == [3]
        assert _tagged_offsets(textbox, 'last') == [4]
        assert _tagged_offsets(textbox, 'clamped') == [3]
        assert textbox.buffer.get_tag_table().lookup('skipped') is None

    def test_insert_translation_inserts_a_plain_string_at_the_cursor(self):
        textbox = self._target_for('%s files copied')
        textbox.set_text('%s files copied')
        textbox.place_cursor(2)
        elem = SimpleNamespace(
            gui_info=SimpleNamespace(get_insert_candidates=lambda: None),
            translate=lambda: ' new')

        assert textbox.insert_translation(elem)

        assert textbox.get_text() == '%s new files copied'
        assert textbox.get_cursor_position() == 6

    def test_insert_candidates_are_not_shown_for_an_unmapped_textbox(self, monkeypatch):
        monkeypatch.setattr(textbox_module.GLib, 'idle_add', lambda func: func())
        textbox = TextBox(self.main_controller, text='%s files')
        elem = SimpleNamespace(gui_info=SimpleNamespace(get_insert_candidates=lambda: ['drank']))

        assert not textbox.insert_translation(elem)

        assert textbox._completion_popup is None

    def test_a_target_out_of_step_with_its_tree_is_rebuilt(self, monkeypatch):
        warnings = []
        monkeypatch.setattr(textbox_module.logging, 'warning', lambda msg, *args: warnings.append(msg))
        textbox = TextBox(self.main_controller, text='%s files')
        textbox.set_visible(True)
        textbox.elem.sub = [StringElem('changed')]

        textbox.buffer.begin_user_action()
        textbox.buffer.end_user_action()

        assert warnings == ['Target text out of step with its placeables: %r']
        assert textbox.get_text() == 'changed'

    def test_deleting_text_the_tree_no_longer_has_is_ignored(self):
        textbox = TextBox(self.main_controller, text='abc')
        textbox.elem.sub = [StringElem('')]
        deleted = []
        textbox.connect('text-deleted', lambda *args: deleted.append(args))

        textbox.buffer.delete(textbox.buffer.get_iter_at_offset(1), textbox.buffer.get_iter_at_offset(2))

        assert deleted == []
        assert str(textbox.elem) == ''

    def test_controllers_registered_after_the_textbox_are_picked_up(self):
        main_controller = _MainController()
        textbox = TextBox(main_controller)
        placeables, undo = object(), object()

        main_controller.register('placeables_controller', placeables)
        main_controller.register('undo_controller', undo)
        main_controller.register('undo_controller', object())

        assert textbox.placeables_controller is placeables
        assert textbox.undo_controller is undo

    def test_editing_before_the_controllers_exist_is_plain_text_editing(self):
        textbox = TextBox(_MainController())
        buffer = textbox.buffer

        buffer.begin_user_action()
        buffer.insert_at_cursor('abc')
        buffer.delete(buffer.get_iter_at_offset(0), buffer.get_iter_at_offset(1))
        buffer.end_user_action()

        assert textbox.get_text() == 'bc'
        assert textbox.elem is None
        elem = StringElem('x')
        textbox.add_default_gui_info(elem)
        assert getattr(elem, 'gui_info', None) is None


class _FakeKeyEvent:
    def __init__(self, keyval, state=0, is_modifier=False):
        self.keyval = keyval
        self._state = state
        self.is_modifier = is_modifier

    def get_state(self):
        return self._state
