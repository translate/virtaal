#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import tempfile

from gi.repository import Gdk, GLib
from test_scaffolding import TestScaffolding
from translate.storage import factory

from virtaal.controllers.placeablescontroller import PlaceablesController


class TestUnitController(TestScaffolding):



    def test_get_target(self):
        # The unit indexes below differ by 1, because the StoreModel class (and thus the rest of Virtaal)
        # ignores PO headers (and other untranslatable units), whereas the Toolkit's stores do not.

        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)

        assert str(self.unit_controller.view.targets[0].elem) == self.trans_store.getunits()[1].target

    def test_set_target(self):
        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)

        self.unit_controller.set_unit_target(0, ['Test',])
        assert str(self.unit_controller.view.targets[0].elem) == 'Test'

    def test_cut_copy_disabled_without_a_selection(self, monkeypatch):
        # #1021: Cut/Copy used to stay enabled the whole time a textbox
        # had focus, regardless of whether anything was selected.
        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)
        monkeypatch.setattr(view.targets[0], 'is_focus', lambda: True)

        view._update_edit_menu_sensitivity()

        assert not view.mnu_cut.get_sensitive()
        assert not view.mnu_copy.get_sensitive()
        assert view.mnu_paste.get_sensitive()  # no selection needed to paste

    def test_cut_copy_enabled_with_a_selection_in_the_target(self, monkeypatch):
        if not getattr(self.main_controller, 'placeables_controller', None):
            PlaceablesController(self.main_controller)

        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)
        target = view.targets[0]
        target.set_text('some text')
        buf = target.get_buffer()
        buf.select_range(buf.get_start_iter(), buf.get_end_iter())
        monkeypatch.setattr(target, 'is_focus', lambda: True)

        view._update_edit_menu_sensitivity()

        assert view.mnu_cut.get_sensitive()
        assert view.mnu_copy.get_sensitive()

    def test_copy_but_not_cut_enabled_for_a_selection_in_a_source(self, monkeypatch):
        # Sources aren't editable - Cut never applies to them, even
        # with text selected.
        if not getattr(self.main_controller, 'placeables_controller', None):
            PlaceablesController(self.main_controller)

        # A different unit than the other tests here use - load_unit()
        # no-ops if asked to reload whatever's already showing, which
        # would leave a stale/empty source buffer since these tests
        # share one UnitController across the whole class.
        test_unit = self.trans_store.getunits()[2]
        view = self.unit_controller.load_unit(test_unit)
        source = view.sources[0]
        buf = source.get_buffer()
        buf.select_range(buf.get_start_iter(), buf.get_end_iter())
        monkeypatch.setattr(source, 'is_focus', lambda: True)

        view._update_edit_menu_sensitivity()

        assert not view.mnu_cut.get_sensitive()
        assert view.mnu_copy.get_sensitive()
        assert not view.mnu_paste.get_sensitive()  # can't paste into a source

    def _assert_initial_cursor_position(self, text, expected_marked):
        """expected_marked is text with a '|' inserted at the offset
        _get_editing_start_pos() is expected to place the cursor at."""
        if not getattr(self.main_controller, 'placeables_controller', None):
            PlaceablesController(self.main_controller)

        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)
        target = view.targets[0]
        target.set_text(text)

        pos = view._get_editing_start_pos(target.elem)

        assert text[:pos] + '|' + text[pos:] == expected_marked

    def test_initial_cursor_skips_a_leading_newline(self):
        # translate/virtaal#1841
        self._assert_initial_cursor_position("\nSome text", "\n|Some text")

    def test_initial_cursor_skips_a_leading_xml_tag(self):
        # translate/virtaal#1841
        self._assert_initial_cursor_position("<b>bold</b>", "<b>|bold</b>")

    def test_initial_cursor_goes_to_the_end_after_a_lone_xml_tag(self):
        self._assert_initial_cursor_position("<b>", "<b>|")

    def test_initial_cursor_skips_a_recognised_python_format_specifier(self):
        # translate/virtaal#1841
        self._assert_initial_cursor_position("%s files copied", "%s| files copied")

    def test_initial_cursor_skips_a_recognised_qt_format_specifier(self):
        self._assert_initial_cursor_position("%1 files copied", "%1| files copied")

    def test_initial_cursor_goes_to_the_end_when_the_whole_string_is_a_placeable(self):
        self._assert_initial_cursor_position("%s", "%s|")

    def test_initial_cursor_lands_mid_token_for_an_unrecognised_percent_sequence(self):
        """#1841's reported "%B" case: %B isn't a valid Python or Qt
        format specifier, so translate-toolkit doesn't recognise it as
        a placeable at all - it's just punctuation followed by a word
        character, and the cursor lands between them. Documenting the
        actual (still slightly awkward) behaviour, not asserting it's
        fixed - it isn't, and it isn't a bug in this function either."""
        self._assert_initial_cursor_position("%B", "%|B")

    def test_advance_workflow_state_on_a_freshly_loaded_unit(self):
        """load_unit() left the state-nav widget's own selection
        unset - move_state() (Ctrl+Enter, Ctrl+Shift+Enter, and the
        Navigation menu's equivalent items) crashed with TypeError on
        the very first attempt on any freshly loaded unit."""
        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)
        view.advance_workflow_state(1)  # must not raise

    def test_stale_alt_down_does_not_corrupt_a_later_unit(self):
        """Alt+Down ('transfer from source') defers its copy via
        GLib.idle_add(). If the loaded unit changes before that runs,
        it must skip rather than overwrite the new unit with the old
        one's source text."""
        if not getattr(self.main_controller, 'placeables_controller', None):
            PlaceablesController(self.main_controller)

        units = self.trans_store.getunits()
        unit_a, unit_b = units[1], units[2]

        self.unit_controller.load_unit(unit_a)
        view = self.unit_controller.view
        textbox = view.targets[0]

        original_b_target = str(unit_b.target)

        # Intercept GLib.idle_add() rather than pumping the real main
        # loop - main-loop pumping has hung CI elsewhere in this
        # codebase. Invoking the captured callback directly tests the
        # real closure with no main-loop involvement at all.
        scheduled = []
        real_idle_add = GLib.idle_add
        GLib.idle_add = lambda callback, *a, **kw: scheduled.append(callback)
        try:
            # Real Alt+Down keypress on unit A.
            textbox.emit('key-pressed', None, 'alt-down')
        finally:
            GLib.idle_add = real_idle_add
        assert scheduled, 'Alt+Down should have scheduled a deferred copy'

        # Navigate to a different unit before that callback runs.
        self.unit_controller.load_unit(unit_b)
        self.store_controller.set_modified(False)

        scheduled[0]()  # run the now-stale callback

        assert str(unit_b.target) == original_b_target
        assert not self.store_controller.is_modified()

    class _FakeReturnEvent:
        keyval = Gdk.KEY_Return
        def get_state(self):
            return Gdk.ModifierType(0)

    def _make_temp_store(self, suffix, contents):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, contents.encode('utf-8'))
        os.close(fd)
        return path

    def _assert_enter_key_survives_plural_unit(self, plural_unit, *rest_units):
        """Exhaust a plural unit's forms with Enter, then walk Enter
        through each of rest_units (mixed types/states) confirming it
        still advances. Shared across formats - see
        test_enter_key_after_plural_unit_still_advances_po for the bug."""
        assert plural_unit.hasplural()
        assert rest_units, "need at least one unit after the plural one to test"
        for u in rest_units:
            assert not u.hasplural()

        self.main_controller.lang_controller.target_lang.nplurals = 2

        # Exhaust the plural unit's two forms - this part already worked
        # before the fix, kept here so a future regression in the
        # *other* direction gets caught too.
        view = self.unit_controller.load_unit(plural_unit)
        view.targets[0].set_text('one file')
        view.targets[0].emit('key-pressed', self._FakeReturnEvent(), 'enter')
        view.targets[1].set_text('N files')

        done_calls = []
        view.connect('editing-done', lambda *a: done_calls.append(a))
        view.targets[1].emit('key-pressed', self._FakeReturnEvent(), 'enter')
        assert done_calls, "Enter on the plural unit's last form should fire editing-done"
        assert view.must_advance

        # Now the real regression: load each *following* unit in turn
        # (standing in for _keyboard_move()/select_index() actually
        # advancing there in the real app) and confirm its own Enter
        # key still works, whatever type or state it is.
        for i, unit in enumerate(rest_units):
            view = self.unit_controller.load_unit(unit)
            assert not view.targets[1].get_parent().props.visible, \
                "targets[1] should be hidden for a non-plural unit"

            view.targets[0].set_text('translated %d' % i)
            done_calls = []
            view.connect('editing-done', lambda *a: done_calls.append(a))
            view.targets[0].emit('key-pressed', self._FakeReturnEvent(), 'enter')

            assert done_calls, (
                "Enter on unit %d (fuzzy=%s) after a plural one should still "
                "fire editing-done, not silently focus a hidden target box"
                % (i, unit.isfuzzy())
            )
            assert view.must_advance

    def test_enter_key_after_plural_unit_still_advances_po(self):
        """Enter on a plural unit's last form used to permanently break
        Enter for every unit after it - see unitview.py's
        target_key_press_event() for the actual fix/why."""
        po_contents = """\
msgid ""
msgstr ""
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "One file"
msgid_plural "%d files"
msgstr[0] ""
msgstr[1] ""

msgid "Second message"
msgstr ""

msgid "Third message"
msgstr ""
"""
        path = self._make_temp_store('.po', po_contents)
        try:
            store = factory.getobject(path)
            units = [u for u in store.units if not u.isheader()]
            # units[1] stands in for "some other type/state", not just
            # "the next plain unit" - see the shared helper's docstring.
            units[1].markfuzzy(True)
            self._assert_enter_key_survives_plural_unit(units[0], units[1], units[2])
        finally:
            os.unlink(path)

    def test_enter_key_after_plural_unit_still_advances_ts(self):
        """Same regression as the PO test above, for Qt Linguist's
        numerus="yes"/numerusform plural mechanism."""
        ts_contents = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="af">
<context>
    <name>Test</name>
    <message numerus="yes">
        <source>%n file(s)</source>
        <translation type="unfinished">
            <numerusform></numerusform>
            <numerusform></numerusform>
        </translation>
    </message>
    <message>
        <source>Second message</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <source>Third message</source>
        <translation type="unfinished"></translation>
    </message>
</context>
</TS>
"""
        path = self._make_temp_store('.ts', ts_contents)
        try:
            store = factory.getobject(path)
            units = list(store.units)
            # units[1] stands in for "some other type/state", not just
            # "the next plain unit" - see the shared helper's docstring.
            units[1].markfuzzy(True)
            self._assert_enter_key_survives_plural_unit(units[0], units[1], units[2])
        finally:
            os.unlink(path)
