#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import tempfile

from gi.repository import Gdk, Gtk

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.test.test_scaffolding import TestScaffolding


class TestStoreView(TestScaffolding):
    def setup_method(self):
        self.store_controller.open_file(self.testfile[1])

    def teardown_method(self):
        self.store_controller.close_file()

    def test_open_file_loads_and_shows_the_store(self):
        view = self.store_controller.view

        assert view.store is self.store_controller.store
        assert view._treeview.get_model() is not None
        assert view.mnu_up.get_sensitive()

    def test_close_file_hides_the_view(self):
        view = self.store_controller.view

        self.store_controller.close_file()

        assert view.parent_widget.props.visible is False
        assert view.store is None
        assert not view.mnu_up.get_sensitive()

    def test_get_store_returns_the_current_store(self):
        view = self.store_controller.view

        assert view.get_store() is self.store_controller.store

    def test_get_unit_celleditor_delegates_to_the_controller(self, monkeypatch):
        view = self.store_controller.view
        calls = []
        monkeypatch.setattr(self.store_controller, 'get_unit_celleditor', lambda unit: calls.append(unit) or 'editor')

        result = view.get_unit_celleditor('some-unit')

        assert calls == ['some-unit']
        assert result == 'editor'

    def test_cursor_change_selects_the_new_index(self, monkeypatch):
        view = self.store_controller.view
        calls = []
        monkeypatch.setattr(view._treeview, 'select_index', lambda i, force=False: calls.append(i))

        view.cursor.index = 1

        assert calls[-1] == 1

    def test_on_style_set_applies_a_background_provider(self):
        view = self.store_controller.view
        first_provider = view._treeview_bg_provider

        view._on_style_set(self.main_controller.view.main_window)

        assert view._treeview_bg_provider is not None
        assert view._treeview_bg_provider is not first_provider

    def test_show_replaces_a_placeholder_child(self):
        view = self.store_controller.view
        view.parent_widget.remove(view._treeview)
        placeholder = Gtk.Label()
        view.parent_widget.add(placeholder)

        view.show()

        assert view._treeview.get_parent() is view.parent_widget
        assert placeholder.get_parent() is None

    def test_show_does_not_select_a_row_without_a_store(self, monkeypatch):
        view = self.store_controller.view
        self.store_controller.close_file()
        calls = []
        monkeypatch.setattr(view._treeview, 'select_index', lambda i, force=False: calls.append(i))

        view.show()

        assert calls == []

    # __init__()'s "main_window already visible" branch (line 40) is
    # deliberately left uncovered: exercising it needs a second,
    # independent MainController/main_window construction while
    # another one is potentially still alive in the same process -
    # confirmed live to segfault (real SIGSEGV inside GTK's own theme
    # reload, gtk_widget_get_screen on an invalid widget), not just an
    # intermittent pytest-xdist worker crash.


PLURAL_LAST_PO = """msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "Open"
msgstr "Oop"

msgid "One file"
msgid_plural "%d files"
msgstr[0] "Een leer"
msgstr[1] "%d leers"
"""


class _ReturnEvent:
    keyval = Gdk.KEY_Return

    def get_state(self):
        return Gdk.ModifierType(0)


def _settle(frames=200):
    for _ in range(frames):
        Gtk.main_iteration_do(False)


class TestEnterOnTheLastUnit(TestScaffolding):
    """Enter with no unit to move to finishes the unit in place (#4087)."""

    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        self.main_controller.lang_controller.target_lang.nplurals = 2
        fd, self.path = tempfile.mkstemp(suffix='.po')
        os.write(fd, PLURAL_LAST_PO.encode('utf-8'))
        os.close(fd)

    def teardown_class(self):
        self.main_controller.view.main_window.hide()
        os.unlink(self.path)
        TestScaffolding.teardown_class(self)

    def test_enter_in_the_last_plural_form_stays_in_that_form(self):
        # It reopened the editor in the first form (#4940).
        self.store_controller.open_file(self.path)
        window = self.main_controller.view.main_window
        window.resize(800, 600)
        window.show()
        _settle()
        self.store_controller.cursor.index = 1
        _settle()
        unit_view = self.unit_controller.view
        assert unit_view.unit.hasplural()

        unit_view.targets[0].emit('key-pressed', _ReturnEvent(), 'enter')
        unit_view.targets[1].emit('key-pressed', _ReturnEvent(), 'enter')
        _settle()

        assert self.store_controller.cursor.index == 1
        assert unit_view.focused_target_n == 1
        assert unit_view.targets[1].is_focus()
