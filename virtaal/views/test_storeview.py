#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.test.test_scaffolding import TestScaffolding
from virtaal.views.storeview import StoreView


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
        monkeypatch.setattr(view._treeview, 'select_index', lambda i: calls.append(i))

        view.cursor.index = 1

        assert calls[-1] == 1

    def test_on_export_reports_a_failure_as_an_error_dialog(self, monkeypatch):
        view = self.store_controller.view
        monkeypatch.setattr(self.store_controller, 'export_project_file',
                             lambda **kw: (_ for _ in ()).throw(ValueError('boom')))
        errors = []
        monkeypatch.setattr(self.main_controller.view, 'show_error_dialog',
                             lambda title='', message='': errors.append((title, message)))

        view._on_export(None)

        assert len(errors) == 1
        assert errors[0][0] == 'Export failed'
        assert 'boom' in errors[0][1]

    def test_on_export_open_reports_a_failure_as_an_error_dialog(self, monkeypatch):
        view = self.store_controller.view
        monkeypatch.setattr(self.store_controller, 'export_project_file',
                             lambda **kw: (_ for _ in ()).throw(ValueError('boom')))
        errors = []
        monkeypatch.setattr(self.main_controller.view, 'show_error_dialog',
                             lambda title='', message='': errors.append((title, message)))

        view._on_export_open(None)

        assert errors[0][0] == 'Export failed'

    def test_on_preview_reports_a_failure_as_an_error_dialog(self, monkeypatch):
        view = self.store_controller.view
        monkeypatch.setattr(self.store_controller, 'export_project_file',
                             lambda **kw: (_ for _ in ()).throw(ValueError('boom')))
        errors = []
        monkeypatch.setattr(self.main_controller.view, 'show_error_dialog',
                             lambda title='', message='': errors.append((title, message)))

        view._on_preview(None)

        assert errors[0][0] == 'Preview failed'

    def test_on_export_succeeds_silently(self, monkeypatch):
        view = self.store_controller.view
        calls = []
        monkeypatch.setattr(self.store_controller, 'export_project_file', lambda **kw: calls.append(kw))

        view._on_export(None)

        assert calls == [{'filename': None}]

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
        monkeypatch.setattr(view._treeview, 'select_index', lambda i: calls.append(i))

        view.show()

        assert calls == []

    def test_hide_resets_the_treeview_column_width(self, monkeypatch):
        view = self.store_controller.view
        calls = []
        monkeypatch.setattr(view._treeview, 'reset_column_width', lambda: calls.append(True))

        view.hide()

        assert calls == [True]


def test_init_applies_style_immediately_when_the_main_window_is_already_visible():
    scaffold = TestScaffolding()
    scaffold.setup_class()
    try:
        scaffold.main_controller.view.main_window.show()

        view = StoreView(scaffold.store_controller)

        assert view._treeview_bg_provider is not None
    finally:
        scaffold.teardown_class()
