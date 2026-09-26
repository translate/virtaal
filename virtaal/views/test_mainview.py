#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regression tests for MainView's native file dialogs.

GtkFileChooserNative (a GtkNativeDialog) returns Gtk.ResponseType.ACCEPT
on accept, never .OK - confirmed against GTK's own docs
(Gtk-3.0.gir: "will return #GTK_RESPONSE_ACCEPT if the user accepted").
show_open_dialog()/show_save_dialog() compared against .OK instead,
which is never returned by a real click - clicking Open/Save silently
did nothing, no error.
"""

from types import SimpleNamespace
from urllib.parse import quote

import gi
import pytest

gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk

from virtaal.common.platform import platform
from virtaal.views.mainview import MainView


class _FakeChooser:
    """Stands in for a GtkFileChooserNative without opening a real
    dialog - only the calls show_open_dialog()/show_save_dialog()
    actually make."""

    def __init__(self, response, filename='/tmp/test.po'):
        self._response = response
        self._filename = filename
        self.title = None

    def set_title(self, title):
        self.title = title

    def set_current_folder(self, folder):
        pass

    def set_current_name(self, name):
        pass

    def set_transient_for(self, window):
        pass

    def run(self):
        return self._response

    def hide(self):
        pass

    def get_filename(self):
        return self._filename

    def get_uri(self):
        return 'file://' + self._filename


def _make_view_with_chooser(attr, chooser):
    view = MainView.__new__(MainView)
    view._top_window = None
    setattr(view, attr, chooser)
    return view


def test_show_open_dialog_returns_filename_on_accept():
    view = _make_view_with_chooser(
        'open_chooser', _FakeChooser(Gtk.ResponseType.ACCEPT))
    filename, uri = view.show_open_dialog()
    assert filename == '/tmp/test.po'


def test_show_open_dialog_returns_nothing_on_cancel():
    view = _make_view_with_chooser(
        'open_chooser', _FakeChooser(Gtk.ResponseType.CANCEL))
    assert view.show_open_dialog() == ()


def test_show_save_dialog_returns_filename_on_accept():
    view = _make_view_with_chooser(
        'save_chooser', _FakeChooser(Gtk.ResponseType.ACCEPT))
    assert view.show_save_dialog('Save', current_filename='/tmp/test.po') == '/tmp/test.po'


def test_report_bug_opens_the_prefilled_template(monkeypatch):
    from virtaal.support import openmailto

    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))

    view = MainView.__new__(MainView)
    view._on_report_bug()

    assert len(opened) == 1
    assert opened[0].startswith(
        'https://github.com/translate/virtaal/issues/new?')
    assert 'template=bug_report.yml' in opened[0]


def test_show_logs_displays_existing_log_content(monkeypatch, tmp_path):
    from virtaal.__version__ import version_string
    from virtaal.common import pan_app

    (tmp_path / 'stdout_virtaal.log').write_text('hello from stdout')
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    monkeypatch.setattr(Gtk.Dialog, 'run', lambda self: Gtk.ResponseType.CLOSE)
    shown = {}
    real_set_text = Gtk.TextBuffer.set_text
    monkeypatch.setattr(
        Gtk.TextBuffer, 'set_text',
        lambda self, text, *args: (shown.setdefault('text', text), real_set_text(self, text, -1))[-1])
    view = MainView.__new__(MainView)
    view.main_window = None

    view._on_show_logs()

    assert shown['text'].startswith('Virtaal %s\n\n' % version_string())
    assert 'hello from stdout' in shown['text']


def test_show_save_dialog_returns_none_on_cancel():
    view = _make_view_with_chooser(
        'save_chooser', _FakeChooser(Gtk.ResponseType.CANCEL))
    assert view.show_save_dialog('Save', current_filename='/tmp/test.po') is None


# _decode_dropped_uri(): drag-and-drop file paths (#3331)

def _dropped(path, encoding='utf-8'):
    return ('file://' + quote(path, encoding=encoding)).encode('utf-8')


def test_decode_dropped_uri_handles_spaces():
    view = MainView.__new__(MainView)
    path = '/tmp/a file with spaces.po'
    assert view._decode_dropped_uri(_dropped(path)) == 'file://' + path


def test_decode_dropped_uri_handles_non_ascii_utf8():
    view = MainView.__new__(MainView)
    path = '/tmp/中文/文件.po'
    assert view._decode_dropped_uri(_dropped(path)) == 'file://' + path


def test_decode_dropped_uri_falls_back_to_system_codepage_on_windows(monkeypatch):
    # Real report (#3331): GTK's Windows DnD backend has been seen to
    # percent-encode non-ASCII file names using the system codepage
    # rather than UTF-8.
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr('locale.getpreferredencoding', lambda do_setlocale=True: 'gbk')

    view = MainView.__new__(MainView)
    path = '/tmp/中文/文件.po'
    assert view._decode_dropped_uri(_dropped(path, encoding='gbk')) == 'file://' + path


def test_decode_dropped_uri_returns_none_for_undecodable_bytes():
    view = MainView.__new__(MainView)
    assert view._decode_dropped_uri(b'\xff\xfe not utf-8') is None


# show_save_confirm_dialog(): dialog focus on macOS (#3525)

class _FakeSaveButton:
    def grab_focus(self):
        pass


class _FakeConfirmDialog:
    def __init__(self):
        self.calls = []
        self._MainView__save_button = _FakeSaveButton()

    def set_transient_for(self, window):
        pass

    def show(self):
        self.calls.append('show')

    def present(self):
        self.calls.append('present')

    def run(self):
        return Gtk.ResponseType.YES

    def hide(self):
        pass


class _FakeTopWindow:
    def __init__(self):
        self.presented = False

    def present(self):
        self.presented = True


def test_show_save_confirm_dialog_shows_before_presenting_and_restores_parent_focus(monkeypatch):
    # present() only raises/focuses an already-realized window - on
    # the very first run() the dialog isn't yet, so show() has to
    # come first or the dialog opens without real OS focus.
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    dialog = _FakeConfirmDialog()
    view.confirm_dialog = dialog
    top_window = _FakeTopWindow()
    view._top_window = top_window

    view.show_save_confirm_dialog()

    assert dialog.calls == ['show', 'present']
    assert top_window.presented
    assert view._top_window is top_window


# quit(): window geometry persisted before Gtk.main_quit()

class _FakeMainWindow:
    def __init__(self, size=(800, 600), position=(10, 20), gdk_window=None):
        self._size = size
        self._position = position
        self._gdk_window = gdk_window

    def get_size(self):
        return self._size

    def get_position(self):
        return self._position

    def get_window(self):
        return self._gdk_window


def _view_for_quit(monkeypatch, maximized=False):
    from virtaal.common import pan_app

    monkeypatch.setattr(pan_app.settings, 'general', {})
    monkeypatch.setattr(pan_app.settings, 'write', lambda: None)
    monkeypatch.setattr(Gtk, 'main_quit', lambda: None)
    view = MainView.__new__(MainView)
    view._window_is_maximized = maximized
    view.main_window = _FakeMainWindow()
    return view


def test_quit_records_maximized_without_reading_window_geometry(monkeypatch):
    from virtaal.common import pan_app

    view = _view_for_quit(monkeypatch, maximized=True)
    view.main_window.get_size = lambda: pytest.fail('should not be read while maximized')
    view.main_window.get_position = lambda: pytest.fail('should not be read while maximized')

    view.quit()

    assert pan_app.settings.general['maximized'] == 1


def test_quit_saves_current_window_geometry_when_not_maximized(monkeypatch):
    from virtaal.common import pan_app

    view = _view_for_quit(monkeypatch, maximized=False)

    view.quit()

    assert pan_app.settings.general['windowwidth'] == 800
    assert pan_app.settings.general['windowheight'] == 600
    assert pan_app.settings.general['windowx'] == 10
    assert pan_app.settings.general['windowy'] == 20
    assert pan_app.settings.general['maximized'] == ''


def test_quit_prefers_geometry_captured_before_hiding(monkeypatch):
    # get_size()/get_position() are unreliable once main_window.hide()
    # has already run - hide() captures geometry beforehand for quit()
    # to use instead of asking the (by then hidden) window directly.
    from virtaal.common import pan_app

    view = _view_for_quit(monkeypatch, maximized=False)
    view._pre_hide_size = (700, 500)
    view._pre_hide_position = (5, 6)
    view.main_window.get_size = lambda: pytest.fail('should use the pre-hide size')
    view.main_window.get_position = lambda: pytest.fail('should use the pre-hide position')

    view.quit()

    assert pan_app.settings.general['windowwidth'] == 700
    assert pan_app.settings.general['windowheight'] == 500
    assert pan_app.settings.general['windowx'] == 5
    assert pan_app.settings.general['windowy'] == 6


def test_quit_calls_gtk_main_quit(monkeypatch):
    view = _view_for_quit(monkeypatch)
    calls = []
    monkeypatch.setattr(Gtk, 'main_quit', lambda: calls.append('quit'))

    view.quit()

    assert calls == ['quit']


# _on_window_state_event() / _restore_pre_fullscreen_size(): native
# fullscreen (macOS green button, Fn+F) restoring the pre-fullscreen
# window size on exit.

class _FakeMenuItem:
    def __init__(self):
        self.active = None

    def set_active(self, value):
        self.active = value


def _view_for_window_state(fullscreen_menu):
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: fullscreen_menu)
    view.main_window = _FakeMainWindow()
    return view


def _state_event(new_state, changed_mask):
    return SimpleNamespace(new_window_state=new_state, changed_mask=changed_mask)


def test_on_window_state_event_activates_the_fullscreen_menu_item():
    menuitem = _FakeMenuItem()
    view = _view_for_window_state(menuitem)

    view._on_window_state_event(view.main_window, _state_event(
        Gdk.WindowState.FULLSCREEN, Gdk.WindowState.FULLSCREEN))

    assert menuitem.active


def test_on_window_state_event_schedules_a_restore_when_leaving_fullscreen(monkeypatch):
    from gi.repository import GLib

    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda delay, func, *args: scheduled.append((delay, func, args)))
    view = _view_for_window_state(_FakeMenuItem())
    view._pre_fullscreen_size = (640, 480)

    view._on_window_state_event(view.main_window, _state_event(
        Gdk.WindowState(0), Gdk.WindowState.FULLSCREEN))

    assert scheduled == [(250, view._restore_pre_fullscreen_size, ((640, 480),))]
    assert view._pre_fullscreen_size is None
    assert view._restoring_from_fullscreen is True


def test_on_window_state_event_does_not_schedule_a_restore_when_entering_fullscreen(monkeypatch):
    from gi.repository import GLib

    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda delay, func, *args: scheduled.append((delay, func, args)))
    view = _view_for_window_state(_FakeMenuItem())
    view._pre_fullscreen_size = (640, 480)

    view._on_window_state_event(view.main_window, _state_event(
        Gdk.WindowState.FULLSCREEN, Gdk.WindowState.FULLSCREEN))

    assert scheduled == []


def test_on_window_state_event_skips_restore_without_a_captured_size(monkeypatch):
    from gi.repository import GLib

    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda delay, func, *args: scheduled.append((delay, func, args)))
    view = _view_for_window_state(_FakeMenuItem())

    view._on_window_state_event(view.main_window, _state_event(
        Gdk.WindowState(0), Gdk.WindowState.FULLSCREEN))

    assert scheduled == []


def test_restore_pre_fullscreen_size_resizes_and_resets_the_column_width():
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow()
    view._restoring_from_fullscreen = True
    resized = []
    view.main_window.resize = lambda w, h: resized.append((w, h))
    reset_calls = []
    view.controller = SimpleNamespace(store_controller=SimpleNamespace(
        store=object(), view=SimpleNamespace(_treeview=SimpleNamespace(
            reset_column_width=lambda: reset_calls.append(1)))))

    result = view._restore_pre_fullscreen_size((1024, 768))

    assert resized == [(1024, 768)]
    assert reset_calls == [1]
    assert result is False
    assert view._restoring_from_fullscreen is False


def test_restore_pre_fullscreen_size_skips_column_reset_without_a_loaded_store():
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow()
    view.main_window.resize = lambda w, h: None
    view.controller = SimpleNamespace(store_controller=SimpleNamespace(store=None))

    view._restore_pre_fullscreen_size((1024, 768))  # must not raise


def test_is_fullscreen_or_restoring_true_while_gdk_reports_fullscreen():
    gdk_window = SimpleNamespace(get_state=lambda: Gdk.WindowState.FULLSCREEN)
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow(gdk_window=gdk_window)
    view._restoring_from_fullscreen = False

    assert view.is_fullscreen_or_restoring() is True


def test_is_fullscreen_or_restoring_true_while_restoring_even_if_not_fullscreen():
    gdk_window = SimpleNamespace(get_state=lambda: Gdk.WindowState(0))
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow(gdk_window=gdk_window)
    view._restoring_from_fullscreen = True

    assert view.is_fullscreen_or_restoring() is True


def test_is_fullscreen_or_restoring_false_for_an_ordinary_window():
    gdk_window = SimpleNamespace(get_state=lambda: Gdk.WindowState(0))
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow(gdk_window=gdk_window)
    view._restoring_from_fullscreen = False

    assert view.is_fullscreen_or_restoring() is False


# _on_store_closed() / _on_store_loaded(): menu sensitivity and the
# recent-files list.

class _FakeSensitiveWidget:
    def __init__(self):
        self.sensitive = []

    def set_sensitive(self, value):
        self.sensitive.append(value)


def _view_for_store_signals():
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    view.main_window = SimpleNamespace(set_title=lambda title: setattr(view, '_title', title))
    return view


def test_on_store_closed_disables_menu_items_and_resets_the_title():
    view = _view_for_store_signals()

    view._on_store_closed(SimpleNamespace())

    assert view.status_bar.sensitive == [False]
    assert view._title == 'Virtaal'


def test_on_store_loaded_enables_binary_export_only_for_a_po_file(monkeypatch):
    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    binary_export = _FakeSensitiveWidget()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: binary_export if name == 'mnu_binary_export' else _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'document.odt', project=None,
        store=SimpleNamespace(filename='/tmp/document.odt'))

    view._on_store_loaded(store_controller)

    assert binary_export.sensitive == []


def test_on_store_loaded_enables_binary_export_for_a_compressed_po_file(monkeypatch):
    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    binary_export = _FakeSensitiveWidget()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: binary_export if name == 'mnu_binary_export' else _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'translations/af.po.gz', project=None,
        store=SimpleNamespace(filename='/tmp/translations/af.po.gz'))

    view._on_store_loaded(store_controller)

    assert binary_export.sensitive == [True]


def test_on_store_loaded_adds_the_bundle_filename_for_a_project(monkeypatch):
    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'bundle.zip', project=True, _archivetemp=False,
        get_bundle_filename=lambda: '/tmp/bundle.zip')

    view._on_store_loaded(store_controller)

    assert added == ['file:///tmp/bundle.zip']


def test_on_store_loaded_adds_the_dropped_uri_when_one_was_recorded(monkeypatch):
    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    view._uri = 'file:///tmp/dropped.po'
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'dropped.po', project=None,
        store=SimpleNamespace(filename='/tmp/dropped.po'))

    view._on_store_loaded(store_controller)

    assert added == ['file:///tmp/dropped.po']


def test_on_store_loaded_adds_an_extra_leading_slash_on_windows(monkeypatch):
    import os

    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(platform, 'is_windows', True)
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'opened.po', project=None,
        store=SimpleNamespace(filename='/tmp/opened.po'))

    view._on_store_loaded(store_controller)

    assert added == ['file:///' + os.path.abspath('/tmp/opened.po')]


# _on_controller_registered(): only the store controller's own
# registration wires up store-closed/store-loaded, and a later
# re-registration disconnects the previous store-loaded handler
# rather than leaking it.

def test_on_controller_registered_ignores_a_different_controller():
    view = MainView.__new__(MainView)
    main_controller = SimpleNamespace(store_controller=object())

    view._on_controller_registered(main_controller, object())  # must not raise


def test_on_controller_registered_connects_store_signals():
    connected = []
    store_controller = SimpleNamespace(connect=lambda signal, handler: connected.append(signal) or signal)
    main_controller = SimpleNamespace(store_controller=store_controller)
    view = MainView.__new__(MainView)

    view._on_controller_registered(main_controller, store_controller)

    assert connected == ['store-closed', 'store-loaded']
    assert view._store_loaded_handler_id == 'store-loaded'


def test_on_controller_registered_disconnects_the_previous_store_loaded_handler():
    disconnected = []
    store_controller = SimpleNamespace(
        connect=lambda signal, handler: signal,
        disconnect=lambda handler_id: disconnected.append(handler_id))
    main_controller = SimpleNamespace(store_controller=store_controller)
    view = MainView.__new__(MainView)
    view._store_loaded_handler_id = 'old-handler-id'

    view._on_controller_registered(main_controller, store_controller)

    assert disconnected == ['old-handler-id']


# find_menu() / find_menu_item(): GTK mnemonic parsing consumes a
# label's leading "_" before get_text() ever sees it, so a caller
# searching by its own "_"-prefixed label relies on the fallback that
# strips the underscore from the search term instead.

def _menu_structure(*labels):
    menubar = Gtk.MenuBar()
    for label in labels:
        menubar.append(Gtk.MenuItem.new_with_mnemonic(label))
    return menubar


def test_find_menu_matches_the_mnemonic_stripped_display_label():
    view = MainView.__new__(MainView)
    view.menu_structure = _menu_structure('_File', '_Edit')

    found = view.find_menu('File')

    assert found.get_child().get_text() == 'File'


def test_find_menu_falls_back_to_stripping_the_search_labels_underscore():
    view = MainView.__new__(MainView)
    view.menu_structure = _menu_structure('_File', '_Edit')

    found = view.find_menu('_Edit')

    assert found.get_child().get_text() == 'Edit'


def test_find_menu_returns_none_for_no_match():
    view = MainView.__new__(MainView)
    view.menu_structure = _menu_structure('_File')

    assert view.find_menu('Nonexistent') is None


def _submenu(*labels):
    parent = Gtk.MenuItem.new_with_mnemonic('_Edit')
    submenu = Gtk.Menu()
    for label in labels:
        submenu.append(Gtk.MenuItem.new_with_mnemonic(label))
    parent.set_submenu(submenu)
    return parent


def test_find_menu_item_matches_the_mnemonic_stripped_display_label():
    view = MainView.__new__(MainView)
    parent = _submenu('Add _Term…')

    item, menu = view.find_menu_item('Add Term…', parent)

    assert menu is parent
    assert item.get_child().get_text() == 'Add Term…'


def test_find_menu_item_falls_back_to_stripping_the_search_labels_underscore():
    view = MainView.__new__(MainView)
    parent = _submenu('Add _Term…')

    item, menu = view.find_menu_item('Add _Term…', parent)

    assert item.get_child().get_text() == 'Add Term…'


def test_find_menu_item_returns_none_for_no_match():
    view = MainView.__new__(MainView)
    parent = _submenu('Add _Term…')

    item, menu = view.find_menu_item('Nonexistent', parent)

    assert (item, menu) == (None, None)


# set_saveable(): the modified-marker/title guard.

def test_set_saveable_skips_redundant_updates_while_already_modified():
    # Repeating this work while already marked modified would flash
    # the window title unnecessarily.
    view = MainView.__new__(MainView)
    view.modified = True
    view.gui = SimpleNamespace(get_object=lambda name: pytest.fail('should not touch any widget'))

    view.set_saveable(True)  # must not raise


def test_set_saveable_marks_the_title_modified():
    save_item = _FakeSensitiveWidget()
    revert_item = _FakeSensitiveWidget()
    widgets = {'mnu_save': save_item, 'mnu_revert': revert_item}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(set_title=lambda title: setattr(view, '_title', title))

    view.set_saveable(True)

    assert save_item.sensitive == [True]
    assert revert_item.sensitive == [True]
    assert view._title == '*document.po - Virtaal'
    assert view.modified is True


def test_set_saveable_clears_the_modified_marker():
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = True
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(set_title=lambda title: setattr(view, '_title', title))

    view.set_saveable(False)

    assert view._title == 'document.po - Virtaal'
    assert view.modified is False


def test_set_saveable_skips_the_title_without_a_filename():
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: None)
    view.main_window = SimpleNamespace(set_title=lambda title: pytest.fail('no filename to show'))

    view.set_saveable(True)  # must not raise


# _setup_key_bindings() #

def _real_view_for_key_bindings():
    """A minimal but real-widget-backed self for _setup_key_bindings() -
    real Gtk.Builder objects support get_children()/remove()/insert()/
    set_accel_group()/set_accel_path() out of the box, unlike a fake."""
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    return SimpleNamespace(gui=builder, main_window=builder.get_object('MainWindow'), sync_menubar=lambda: None)


def test_setup_key_bindings_registers_preferences_with_ctrl_p_off_mac(monkeypatch):
    # Spies on the call rather than checking Gtk.AccelMap's own
    # resulting state: that's real global process state, and
    # add_entry() is a no-op once a path already has an entry - two
    # tests toggling is_mac against the same path would contaminate
    # each other regardless of run order.
    monkeypatch.setattr(platform, 'is_mac', False)
    calls = []
    monkeypatch.setattr(Gtk.AccelMap, 'add_entry', lambda path, key, mods: calls.append((path, key, mods)))
    view = _real_view_for_key_bindings()

    MainView._setup_key_bindings(view)

    assert ("<Virtaal>/Edit/Preferences", Gdk.KEY_p, Gdk.ModifierType.CONTROL_MASK) in calls


def test_setup_key_bindings_leaves_preferences_alone_on_mac(monkeypatch):
    # macOS keeps its own conventional Cmd+, from virtaal.accel, loaded
    # separately in _setup_macos_integration() - this function must not
    # also register Preferences itself when is_mac.
    monkeypatch.setattr(platform, 'is_mac', True)
    calls = []
    monkeypatch.setattr(Gtk.AccelMap, 'add_entry', lambda path, key, mods: calls.append((path, key, mods)))
    view = _real_view_for_key_bindings()

    MainView._setup_key_bindings(view)

    assert not any(path == "<Virtaal>/Edit/Preferences" for path, key, mods in calls)


# show_template_update_notice(): dismissable "Update from Template" stats
# notice, replacing a blocking modal dialog (#3808).

class _FakeVboxMain:
    def __init__(self):
        self.packed = []

    def pack_start(self, widget, expand, fill, padding):
        self.packed.append(widget)

    def reorder_child(self, widget, position):
        pass


def _view_for_template_update_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    return view, vbox


def test_show_template_update_notice_packs_a_dismissable_infobar():
    view, vbox = _view_for_template_update_notice()

    view.show_template_update_notice('File Updated', 'Before:\n\tTranslated: 1')

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.INFO
    assert infobar.get_show_close_button() is True


def test_show_template_update_notice_replaces_a_previous_one():
    view, vbox = _view_for_template_update_notice()
    view.show_template_update_notice('First', 'msg')
    first = view._template_update_infobar

    view.show_template_update_notice('Second', 'msg2')

    assert len(vbox.packed) == 2
    assert view._template_update_infobar is not first
    assert first.get_parent() is None  # destroyed, not just replaced in our own attribute


def test_show_template_update_notice_dismiss_clears_the_tracked_infobar():
    view, vbox = _view_for_template_update_notice()
    view.show_template_update_notice('File Updated', 'msg')
    infobar = view._template_update_infobar

    infobar.emit('response', Gtk.ResponseType.CLOSE)

    assert view._template_update_infobar is None
