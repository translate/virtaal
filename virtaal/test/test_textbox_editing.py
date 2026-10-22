#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Placeable editing through a target TextBox's real keystroke paths -
GTK's key bindings and input-method commit - with undo and redo through
the real UndoController."""

import random

import pytest
from gi.repository import GLib, Gtk
from test_scaffolding import TestScaffolding
from translate.storage import factory
from translate.storage.placeables import base, general

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views.widgets import textbox as textbox_module

PLACEABLES_PO = "devsupport/testfiles/placeables.po"
PLACEABLES_XLIFF = "devsupport/testfiles/placeables.xliff"

_ONE_UNIT_PO = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "Coffee"\nmsgstr "%s"\n'

# Text GTK lays out as clusters of several code points.
CLUSTER_TEXTS = [
    'ক্ষমা',  # Bengali conjunct
    'हिंदी',  # Devanagari
    'بَيْت',  # Arabic harakat
    'กี่',  # Thai tone mark
    'שָׁלוֹם',  # Hebrew niqqud
    'Việt',  # NFC
    'Việt',  # NFD
    '한국',  # NFD 한국
]
NESTED_G_XLIFF = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original="test" source-language="en" target-language="af" datatype="plaintext">
<body><trans-unit id="1">
<source>A <g id="1">x <x id="2"/> y</g> b</source>
<target>A <g id="1">x <x id="2"/> y</g> b</target>
</trans-unit></body>
</file>
</xliff>
"""


class _Editor:
    """Edits a target the way a translator does, checking after every step
        that the buffer still shows the target's placeable tree."""

    def __init__(self, test, textbox):
        self.test = test
        self.textbox = textbox
        self.buffer = textbox.buffer

    def run_idle(self):
        while self.test.idle_calls:
            self.test.idle_calls.pop(0)()

    def check(self):
        textbox, buffer = self.textbox, self.buffer
        assert self.test.warnings == []
        assert textbox.get_text() == str(textbox.elem)
        assert textbox.elem.gui_info.length() == buffer.get_char_count()
        assert not textbox._is_inside_newline(buffer.get_iter_at_mark(buffer.get_insert()))

    def type(self, text):
        for char in text:
            self.commit(char)

    def commit(self, text):
        # What GtkTextView's input-method commit does - one keystroke, or
        # a whole syllable from an input method that commits clusters.
        self.buffer.begin_user_action()
        self.buffer.delete_selection(True, True)
        self.buffer.insert_interactive_at_cursor(text, -1, True)
        self.buffer.end_user_action()
        self.run_idle()
        self.check()

    def backspace(self, times=1):
        for _ in range(times):
            self.textbox.emit('backspace')
            self.run_idle()
            self.check()

    def delete(self, times=1):
        for _ in range(times):
            self.textbox.emit('delete-from-cursor', Gtk.DeleteType.CHARS, 1)
            self.run_idle()
            self.check()

    def arrow(self, count, shift=False):
        self.textbox.emit('move-cursor', Gtk.MovementStep.LOGICAL_POSITIONS, count, shift)
        self.run_idle()
        self.check()

    def place(self, offset):
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(offset))

    def select(self, start, end):
        self.buffer.select_range(self.buffer.get_iter_at_offset(end), self.buffer.get_iter_at_offset(start))

    def undo(self):
        self.test.undo_controller._on_undo_activated()
        self.run_idle()
        self.check()

    def redo(self):
        self.test.undo_controller._on_redo_activated()
        self.run_idle()
        self.check()

    @property
    def cursor(self):
        return self.buffer.props.cursor_position

    @property
    def text(self):
        return str(self.textbox.elem)


class TestTextBoxEditing(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)

    @pytest.fixture(autouse=True)
    def _main_loop(self, monkeypatch):
        # Pumping the real main loop hangs in this suite - run idle
        # callbacks from the editor instead.
        self.idle_calls = []
        monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: self.idle_calls.append(lambda: func(*args)))
        undo = self.undo_controller
        # Every edit stays on one unit: no store cursor to navigate with.
        monkeypatch.setattr(undo, '_select_unit', lambda unit: undo._flush_pending_refresh())
        monkeypatch.setattr(undo, '_correct_state_after_undo_redo', lambda unit=None: None)
        self.warnings = []
        monkeypatch.setattr(textbox_module.logging, 'warning', lambda msg, *args: self.warnings.append(msg % args))

    def _editor(self, path, index):
        # A fresh store each time: load_unit() ignores the unit already loaded.
        unit = factory.getobject(path).getunits()[index]
        for textbox in self.unit_controller.view.targets:
            textbox._suggestion = None
        view = self.unit_controller.load_unit(unit)
        view._layout_update_targets()
        self.undo_controller.model.clear()
        editor = _Editor(self, view.targets[0])
        editor.check()
        return editor

    def _placeables(self, editor):
        return [e for e in editor.textbox.elem.depth_first() if isinstance(e, general.PythonFormattingPlaceable)]

    def _g(self, editor):
        return [e for e in editor.textbox.elem.depth_first() if isinstance(e, base.G)]

    # XLIFF unit 0, "Click <g>here</g> to continue.": "<1|" at 6, "here"
    # at 7-10, ">" at 11.

    def test_deleting_all_of_a_gs_text_keeps_the_g(self):
        # #1302, #3325
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(11)

        editor.backspace(4)

        assert editor.text == 'Click  to continue.'
        assert len(self._g(editor)) == 1

    def test_typing_into_an_emptied_g_puts_the_text_inside_it(self):
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(11)
        editor.backspace(4)

        editor.type('XY')

        assert str(self._g(editor)[0]) == 'XY'

    def test_undo_puts_deleted_text_back_inside_the_g(self):
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(11)
        editor.backspace(4)
        editor.type('XY')

        for _ in range(6):
            editor.undo()

        assert str(self._g(editor)[0]) == 'here'
        assert editor.text == 'Click here to continue.'

    def test_typing_over_a_gs_selected_text_keeps_the_g(self):
        # #3325
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.select(7, 11)

        editor.type('X')

        assert str(self._g(editor)[0]) == 'X'
        assert editor.text == 'Click X to continue.'

    def test_typing_inside_a_g_inserts(self):
        # #2087
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(8)

        editor.type('Z')

        assert str(self._g(editor)[0]) == 'hZere'

    def test_undo_restores_text_deleted_inside_a_g_after_deleting_the_g(self):
        # #1303
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(9)
        editor.backspace()
        editor.place(6)
        editor.delete()
        assert editor.text == 'Click  to continue.'

        editor.undo()
        editor.undo()

        assert editor.text == 'Click here to continue.'
        assert str(self._g(editor)[0]) == 'here'

    def test_deleting_text_after_a_g_keeps_the_cursor_after_it(self):
        # #1304
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(editor.buffer.get_char_count())

        editor.backspace(len(' to continue.'))

        assert editor.cursor == 12

    def test_typing_at_the_inside_end_of_a_tag_puts_the_text_inside_it(self):
        # "An <it>opening</it> isolated tag.": the end widget is at 11.
        editor = self._editor(PLACEABLES_XLIFF, 4)
        editor.place(11)

        editor.type('s')

        assert editor.text == 'An openings isolated tag.'
        assert str(editor.textbox.elem.sub[1]) == 'openings'

    # NESTED_G_XLIFF, "A <g>x <x/> y</g> b": "<1|" at 2, "x " at 3-4, the
    # <x/> at 5, " y" at 6-7, "|1>" at 8.

    def _nested_g_editor(self, tmp_path):
        path = tmp_path / 'nested.xlf'
        path.write_text(NESTED_G_XLIFF)
        return self._editor(str(path), 0)

    def test_typing_at_the_inside_start_of_a_g_holding_a_placeable(self, tmp_path):
        editor = self._nested_g_editor(tmp_path)
        editor.place(3)

        editor.type('Z')

        assert editor.text == 'A Zx  y b'
        assert str(self._g(editor)[0]) == 'Zx  y'

    def test_typing_at_the_inside_end_of_a_g_holding_a_placeable(self, tmp_path):
        editor = self._nested_g_editor(tmp_path)
        editor.place(8)

        editor.type('Z')

        assert editor.text == 'A x  yZ b'
        assert str(self._g(editor)[0]) == 'x  yZ'

    def test_typing_inside_a_locked_g_changes_nothing(self, tmp_path):
        editor = self._nested_g_editor(tmp_path)
        self._g(editor)[0].iseditable = False
        editor.place(3)

        editor.type('Z')

        assert editor.text == 'A x  y b'

    def test_deleting_an_x_can_be_undone(self):
        # "A line break<x/>after it.": X has a widget and no text.
        editor = self._editor(PLACEABLES_XLIFF, 1)
        editor.place(12)

        editor.delete()
        assert editor.buffer.get_char_count() == len('A line breakafter it.')

        editor.undo()
        assert editor.buffer.get_char_count() == len('A line breakafter it.') + 1

    def test_a_selection_ending_inside_a_tags_widget_keeps_the_tag(self):
        # "A placeholder: <ph>CODE</ph> here.": GTK can't delete only one
        # of the tag's widgets.
        editor = self._editor(PLACEABLES_XLIFF, 3)

        editor.select(1, 17)
        editor.delete()

        assert editor.text == 'AODE here.'

    # PO placeables are parsed from the text, so editing inside one edits
    # its text.

    def test_typing_inside_a_placeable_edits_its_text(self):
        editor = self._editor(PLACEABLES_PO, 6)  # "%(count)s files renamed"
        editor.place(5)

        editor.type('X')

        assert editor.text == '%(couXnt)s files renamed'

    def test_deleting_inside_a_placeable_edits_its_text(self):
        editor = self._editor(PLACEABLES_PO, 2)  # an e-mail address
        editor.place(len('Contact us at translate'))

        editor.backspace(3)

        assert editor.text == 'Contact us at transl-devel@lists.sourceforge.net.'

    def test_breaking_a_placeable_makes_it_plain_text_until_it_is_whole_again(self):
        editor = self._editor(PLACEABLES_PO, 6)  # "%(count)s files renamed"
        editor.place(len('%(count)'))

        editor.backspace()
        assert not self._placeables(editor)

        editor.type(')')
        assert [str(e) for e in self._placeables(editor)] == ['%(count)s']

    def test_undo_restores_text_deleted_inside_a_placeable(self):
        editor = self._editor(PLACEABLES_PO, 6)
        editor.place(5)
        editor.backspace()
        editor.delete()

        editor.undo()
        editor.undo()

        assert editor.text == '%(count)s files renamed'

    def test_redo_puts_the_cursor_where_the_deletion_was(self):
        editor = self._editor(PLACEABLES_XLIFF, 0)
        editor.place(10)
        editor.backspace()

        editor.undo()
        editor.redo()

        assert editor.cursor == 9

    # PO unit 0, "First line.\nSecond line.": the pilcrow is at 11, the
    # line break at 12 (#3830).

    def test_right_arrow_steps_over_a_newline(self):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(11)

        editor.arrow(1)

        assert editor.cursor == 13

    def test_left_arrow_stops_before_a_newline(self):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(13)

        editor.arrow(-1)

        assert editor.cursor == 11

    def test_shift_right_selects_the_whole_newline(self):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(11)

        editor.arrow(1, shift=True)

        assert [i.get_offset() for i in editor.buffer.get_selection_bounds()] == [11, 13]

    def test_a_click_between_the_pilcrow_and_line_break_types_at_the_line_end(self):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(5)
        editor.place(12)

        editor.type('X')

        assert editor.text == 'First line.X\nSecond line.'
        assert editor.cursor == len('First line.X')

    def test_backspace_after_a_newline_removes_it(self):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(13)

        editor.backspace()

        assert editor.text == 'First line.Second line.'

    @pytest.mark.parametrize('typed, left', [
        ('কি', 'ক'),  # Bengali consonant + vowel sign
        ('ক্ষি', 'ক্ষ'),  # Bengali conjunct + vowel sign
        ('हिंदी', 'हिंद'),  # Devanagari
        ('بَ', 'ب'),  # Arabic letter + fatha (#986)
    ])
    def test_backspace_after_a_combining_mark_deletes_only_the_mark(self, typed, left):
        editor = self._editor(PLACEABLES_PO, 0)
        editor.place(editor.buffer.get_char_count())
        editor.type(typed)

        editor.backspace()

        assert editor.text == 'First line.\nSecond line.' + left

        editor.undo()

        assert editor.text == 'First line.\nSecond line.' + typed

        editor.redo()

        assert editor.text == 'First line.\nSecond line.' + left

    # Pango deletes a Latin, Greek or Cyrillic letter together with its
    # marks.

    @pytest.mark.parametrize('typed, left', [
        ('é', ''),  # NFD é
        ('Việ', 'Vi'),  # NFD ệ
        ('ά', ''),  # NFD ά
        ('й', ''),  # NFD й
    ])
    def test_backspace_after_a_latin_combining_mark_deletes_the_whole_letter(self, typed, left):
        editor = self._editor(PLACEABLES_PO, 0)
        original = editor.text
        editor.place(editor.buffer.get_char_count())
        editor.type(typed)

        editor.backspace()

        assert editor.text == original + left

        editor.undo()

        assert editor.text == original + typed

        editor.redo()

        assert editor.text == original + left

    @pytest.mark.parametrize('cluster', [
        'कि',  # Devanagari consonant + vowel sign
        'กี่',  # Thai consonant + vowel + tone mark
        'שָׁ',  # Hebrew shin + qamats + shin dot
        'é',  # NFD é
        '한',  # NFD 한
    ])
    def test_delete_before_a_cluster_removes_all_of_it(self, cluster):
        editor = self._editor(PLACEABLES_PO, 0)
        original = editor.text
        start = editor.buffer.get_char_count()
        editor.place(start)
        editor.type(cluster + 'x')
        editor.place(start)

        editor.delete()

        assert editor.text == original + 'x'

        editor.undo()

        assert editor.text == original + cluster + 'x'

        editor.redo()

        assert editor.text == original + 'x'

    @pytest.mark.parametrize('text', ['ক্ষি', 'Việt', 'שָׁלוֹם'])
    def test_typing_over_selected_marks_replaces_all_of_them(self, text):
        editor = self._editor(PLACEABLES_PO, 0)
        original = editor.text
        start = editor.buffer.get_char_count()
        editor.place(start)
        editor.type(text)
        editor.select(start, start + len(text))

        editor.type('X')

        assert editor.text == original + 'X'

        editor.undo()

        assert editor.text == original + text

        editor.redo()

        assert editor.text == original + 'X'

    @pytest.mark.parametrize('text', CLUSTER_TEXTS)
    def test_an_input_method_commit_undoes_and_redoes_in_one_step(self, text):
        editor = self._editor(PLACEABLES_PO, 0)
        original = editor.text
        editor.place(editor.buffer.get_char_count())

        editor.commit(text)

        assert editor.text == original + text

        editor.undo()

        assert editor.text == original

        editor.redo()

        assert editor.text == original + text

    @pytest.mark.parametrize('text', CLUSTER_TEXTS)
    def test_undoing_and_redoing_typed_marks_keeps_every_code_point(self, text):
        editor = self._editor(PLACEABLES_PO, 0)
        original = editor.text
        editor.place(editor.buffer.get_char_count())
        editor.type(text)

        for _ in text:
            editor.undo()

        assert editor.text == original

        for _ in text:
            editor.redo()

        assert editor.text == original + text

    def test_editing_keeps_each_parts_own_normalisation_form(self, tmp_path):
        path = tmp_path / 'nfd.po'
        path.write_text(_ONE_UNIT_PO % 'Café %s', encoding='utf-8')
        editor = self._editor(str(path), 0)
        editor.place(editor.buffer.get_char_count())

        editor.type(' café')

        assert editor.text == 'Café %s café'
        assert self.unit_controller.current_unit.target == 'Café %s café'

    # Random edits: whatever a translator does, the buffer keeps showing
    # the tree, undoing everything gets the original back and redoing
    # everything gets the last text back.

    @pytest.mark.parametrize('seed', range(40))
    def test_random_edits(self, seed):
        rnd = random.Random(seed)
        path = rnd.choice([PLACEABLES_PO, PLACEABLES_XLIFF])
        editor = self._editor(path, rnd.randrange(len(factory.getobject(path).getunits())))
        original = editor.text
        for _ in range(30):
            length = editor.buffer.get_char_count()
            action = rnd.choice(['type', 'type', 'placeable', 'newline', 'backspace', 'delete',
                                 'place', 'arrow', 'select-delete', 'select-type', 'undo', 'redo'])
            if action == 'type':
                editor.type(rnd.choice('ab '))
            elif action == 'placeable':
                editor.type(rnd.choice(['%s', '%d', '{0}', '<b>', '</b>', '&amp;']))
            elif action == 'newline':
                editor.type('\n')
            elif action == 'backspace':
                editor.backspace()
            elif action == 'delete':
                editor.delete()
            elif action == 'place':
                editor.place(rnd.randint(0, length))
            elif action == 'arrow':
                editor.arrow(rnd.choice([-1, 1]), shift=rnd.random() < 0.3)
            elif action.startswith('select'):
                editor.select(*sorted((rnd.randint(0, length), rnd.randint(0, length))))
                editor.type('z') if action == 'select-type' else editor.delete()
            elif action == 'undo' and self.undo_controller.model.can_undo():
                editor.undo()
            elif action == 'redo' and self.undo_controller.model.can_redo():
                editor.redo()

        while self.undo_controller.model.can_redo():
            editor.redo()
        final = editor.text
        while self.undo_controller.model.can_undo():
            editor.undo()
        assert editor.text == original
        while self.undo_controller.model.can_redo():
            editor.redo()
        assert editor.text == final
