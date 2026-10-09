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

import ctypes
import os
import sys
from types import SimpleNamespace
from urllib.parse import quote

import gi
import pytest

gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk

from virtaal.common.platform import platform
from virtaal.views import mainview
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


def test_template_chooser_only_offers_pot_files():
    view = MainView.__new__(MainView)
    view.main_window = None

    filters = view.template_chooser.list_filters()
    assert len(filters) == 1
    _name, entries = filters[0].to_gvariant()
    assert {pattern for _type, pattern in entries} == {'*.pot', '*.pot.gz', '*.pot.bz2'}


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
    view.main_window = Gtk.Window()

    view._on_show_logs()

    assert shown['text'].startswith('Virtaal %s\n\n' % version_string())
    assert 'hello from stdout' in shown['text']


def test_show_logs_restores_main_window_focus_on_close(monkeypatch, tmp_path):
    from gi.repository import GLib

    from virtaal.common import pan_app

    (tmp_path / 'stdout_virtaal.log').write_text('hello from stdout')
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    monkeypatch.setattr(Gtk.Dialog, 'run', lambda self: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))

    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()
    calls = []
    monkeypatch.setattr(view.main_window, 'present', lambda: calls.append('present'))

    view._on_show_logs()

    assert calls == ['present']


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


# show_prompt_dialog()/show_error_dialog()/show_info_dialog(): same
# missing-focus bug as show_save_confirm_dialog() (#3865)

class _FakeMessageDialog:
    def __init__(self, response=Gtk.ResponseType.YES):
        self.calls = []
        self._response = response

    def set_title(self, title):
        pass

    def set_markup(self, markup):
        pass

    def set_transient_for(self, window):
        pass

    def show(self):
        self.calls.append('show')

    def present(self):
        self.calls.append('present')

    def run(self):
        return self._response

    def hide(self):
        pass


def test_show_prompt_dialog_shows_before_presenting_and_restores_parent_focus(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    dialog = _FakeMessageDialog(response=Gtk.ResponseType.YES)
    view.prompt_dialog = dialog
    top_window = _FakeTopWindow()
    view._top_window = top_window

    result = view.show_prompt_dialog(message='Reload the file?')

    assert dialog.calls == ['show', 'present']
    assert top_window.presented
    assert view._top_window is top_window
    assert result is True


def test_show_error_dialog_shows_before_presenting_and_restores_parent_focus(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    dialog = _FakeMessageDialog(response=Gtk.ResponseType.OK)
    view.error_dialog = dialog
    top_window = _FakeTopWindow()
    view._top_window = top_window

    view.show_error_dialog(message='Could not open file.')

    assert dialog.calls == ['show', 'present']
    assert top_window.presented
    assert view._top_window is top_window


def test_show_info_dialog_shows_before_presenting_and_restores_parent_focus(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    dialog = _FakeMessageDialog(response=Gtk.ResponseType.OK)
    view.info_dialog = dialog
    top_window = _FakeTopWindow()
    view._top_window = top_window

    view.show_info_dialog(message='Done.')

    assert dialog.calls == ['show', 'present']
    assert top_window.presented
    assert view._top_window is top_window


class _FakeInputDialog:
    def __init__(self, response=Gtk.ResponseType.OK, text='typed'):
        self._response = response
        self._text = text

    def set_transient_for(self, window):
        pass

    def run(self, title=None, message=None):
        return self._response, self._text

    def hide(self):
        pass


def test_show_input_dialog_restores_parent_focus(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    view.input_dialog = _FakeInputDialog()
    top_window = _FakeTopWindow()
    view._top_window = top_window

    result = view.show_input_dialog(message='How many plural forms?')

    assert top_window.presented
    assert view._top_window is top_window
    assert result == 'typed'


class _FakeEntryDialogEntry:
    def set_text(self, text):
        pass

    def get_text(self):
        return ''

    def grab_focus(self):
        pass


def test_entry_dialog_run_presents_before_grabbing_focus(monkeypatch):
    # present() only raises/focuses an already-realized window - it has
    # to come after show_all(), matching every other dialog fixed for
    # the same macOS AX-focus bug (#3865).
    from virtaal.views.mainview import EntryDialog
    dialog = EntryDialog.__new__(EntryDialog)
    dialog.ent_input = _FakeEntryDialogEntry()
    calls = []
    dialog.show_all = lambda: calls.append('show_all')
    dialog.present = lambda: calls.append('present')
    monkeypatch.setattr(Gtk.Dialog, 'run', lambda self: Gtk.ResponseType.CANCEL)

    dialog.run()

    assert calls == ['show_all', 'present']


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


def test_restore_pre_fullscreen_size_resizes():
    view = MainView.__new__(MainView)
    view.main_window = _FakeMainWindow()
    resized = []
    view.main_window.resize = lambda w, h: resized.append((w, h))

    result = view._restore_pre_fullscreen_size((1024, 768))

    assert resized == [(1024, 768)]
    assert result is False


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
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
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
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
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
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'bundle.zip', project=True,
        get_bundle_filename=lambda: '/tmp/bundle.zip')

    view._on_store_loaded(store_controller)

    assert added == ['file:///tmp/bundle.zip']


def test_on_store_loaded_adds_the_store_filename_even_with_a_stale_uri_set(monkeypatch):
    # store_controller.store.filename, not self._uri: some open_file()
    # callers (the welcome screen's recent-files list, the macOS Dock's
    # own openFile: event) never set self._uri, leaving it stale from
    # whatever a *different*, earlier open last set it to - it must
    # never be trusted here even when it happens to be set (#3863).
    import os

    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    monkeypatch.setattr(platform, 'is_windows', False)
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    view._uri = 'file:///tmp/stale-from-an-earlier-open.po'
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'dropped.po', project=None,
        store=SimpleNamespace(filename='/tmp/dropped.po'))

    view._on_store_loaded(store_controller)

    assert added == ['file://' + os.path.abspath('/tmp/dropped.po')]


def test_on_store_loaded_adds_an_extra_leading_slash_on_windows(monkeypatch):
    import os

    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    monkeypatch.setattr(platform, 'is_windows', True)
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'opened.po', project=None,
        store=SimpleNamespace(filename='/tmp/opened.po'))

    view._on_store_loaded(store_controller)

    assert added == ['file:///' + os.path.abspath('/tmp/opened.po')]


# _on_store_saved(): a plain save or a Save As also refreshes the
# recent-files list and macOS Dock entry (#3902) - previously only
# _on_store_loaded() did, so the new filename picked in a Save As
# dialog (including one forced by a .pot template's first save, or by
# #517's read-only-file redirect) never showed up in Recent Files.

def test_on_store_saved_adds_the_bundle_filename_for_a_project(monkeypatch):
    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    view = MainView.__new__(MainView)
    store_controller = SimpleNamespace(
        project=True, get_bundle_filename=lambda: '/tmp/bundle.zip')

    view._on_store_saved(store_controller)

    assert added == ['file:///tmp/bundle.zip']


def test_on_store_saved_adds_the_current_store_filename(monkeypatch):
    import os

    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    monkeypatch.setattr(platform, 'is_windows', False)
    view = MainView.__new__(MainView)
    store_controller = SimpleNamespace(
        project=None, store=SimpleNamespace(filename='/tmp/save-as-target.po'))

    view._on_store_saved(store_controller)

    assert added == ['file://' + os.path.abspath('/tmp/save-as-target.po')]


def test_on_store_saved_adds_an_extra_leading_slash_on_windows(monkeypatch):
    import os

    from virtaal.views import recent
    added = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: added.append(uri)))
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: None)
    monkeypatch.setattr(platform, 'is_windows', True)
    view = MainView.__new__(MainView)
    store_controller = SimpleNamespace(
        project=None, store=SimpleNamespace(filename='/tmp/save-as-target.po'))

    view._on_store_saved(store_controller)

    assert added == ['file:///' + os.path.abspath('/tmp/save-as-target.po')]


def test_on_store_saved_notes_the_store_filename_on_mac(monkeypatch):
    import os

    from virtaal.views import recent
    noted = []
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    monkeypatch.setattr(platform, 'is_mac', True)
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: noted.append(path))
    view = MainView.__new__(MainView)
    store_controller = SimpleNamespace(
        project=None, store=SimpleNamespace(filename='/tmp/save-as-target.po'))

    view._on_store_saved(store_controller)

    assert noted == [os.path.abspath('/tmp/save-as-target.po')]


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

    assert connected == ['store-closed', 'store-loaded', 'store-saved']
    assert view._store_loaded_handler_id == 'store-loaded'
    assert view._store_saved_handler_id == 'store-saved'


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


def test_set_saveable_marks_the_title_modified(monkeypatch):
    monkeypatch.setattr(platform, 'use_app_name_in_title', lambda: True)
    save_item = _FakeSensitiveWidget()
    revert_item = _FakeSensitiveWidget()
    widgets = {'mnu_save': save_item, 'mnu_revert': revert_item}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(
        set_title=lambda title: setattr(view, '_title', title), get_window=lambda: None)

    view.set_saveable(True)

    assert save_item.sensitive == [True]
    assert revert_item.sensitive == [True]
    assert view._title == '*document.po - Virtaal'
    assert view.modified is True


def test_set_saveable_clears_the_modified_marker(monkeypatch):
    monkeypatch.setattr(platform, 'use_app_name_in_title', lambda: True)
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = True
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(
        set_title=lambda title: setattr(view, '_title', title), get_window=lambda: None)

    view.set_saveable(False)

    assert view._title == 'document.po - Virtaal'
    assert view.modified is False


def test_set_saveable_omits_the_app_name_when_the_platform_says_so(monkeypatch):
    # e.g. a frozen macOS .app - the Dock/Cmd-Tab already show "Virtaal".
    monkeypatch.setattr(platform, 'use_app_name_in_title', lambda: False)
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(
        set_title=lambda title: setattr(view, '_title', title), get_window=lambda: None)

    view.set_saveable(True)

    assert view._title == '*document.po'


def test_set_saveable_skips_the_title_without_a_filename():
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: None)
    view.main_window = SimpleNamespace(
        set_title=lambda title: pytest.fail('no filename to show'), get_window=lambda: None)

    view.set_saveable(True)  # must not raise


def test_set_saveable_skips_the_title_star_when_the_native_marker_works(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)
    monkeypatch.setattr(mainview, '_set_document_edited', lambda gdk_window, edited: None)
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(
        set_title=lambda title: setattr(view, '_title', title), get_window=lambda: object())

    view.set_saveable(True)

    assert view._title == 'document.po - Virtaal'


def test_set_saveable_falls_back_to_the_title_star_when_the_native_marker_fails(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)

    def _raise(gdk_window, edited):
        raise OSError('no such symbol')
    monkeypatch.setattr(mainview, '_set_document_edited', _raise)
    widgets = {'mnu_save': _FakeSensitiveWidget(), 'mnu_revert': _FakeSensitiveWidget()}
    view = MainView.__new__(MainView)
    view.modified = False
    view.gui = SimpleNamespace(get_object=lambda name: widgets[name])
    view.controller = SimpleNamespace(get_store_filename=lambda: '/tmp/document.po')
    view.main_window = SimpleNamespace(
        set_title=lambda title: setattr(view, '_title', title), get_window=lambda: object())

    view.set_saveable(True)

    assert view._title == '*document.po - Virtaal'


# _update_document_edited(): the native macOS unsaved-changes marker #

def test_update_document_edited_noop_off_mac(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(mainview, '_set_document_edited',
        lambda gdk_window, edited: pytest.fail('should not touch the native window off mac'))
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(
        get_window=lambda: pytest.fail('should not be read off mac'))

    view._update_document_edited(True)  # must not raise


def test_update_document_edited_noop_without_a_realized_window(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)
    monkeypatch.setattr(mainview, '_set_document_edited',
        lambda gdk_window, edited: pytest.fail('should not touch a nonexistent window'))
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(get_window=lambda: None)

    view._update_document_edited(True)  # must not raise


def test_update_document_edited_calls_the_native_setter(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)
    gdk_window = object()
    calls = []
    monkeypatch.setattr(mainview, '_set_document_edited',
        lambda window, edited: calls.append((window, edited)))
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(get_window=lambda: gdk_window)

    view._update_document_edited(True)

    assert calls == [(gdk_window, True)]


def test_update_document_edited_swallows_native_setter_errors(monkeypatch):
    # The underlying ctypes calls reach into undocumented GDK/AppKit
    # internals - a failure there shouldn't crash the save path.
    monkeypatch.setattr(platform, 'is_mac', True)

    def _raise(gdk_window, edited):
        raise OSError('no such symbol')
    monkeypatch.setattr(mainview, '_set_document_edited', _raise)
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(get_window=lambda: object())

    view._update_document_edited(True)  # must not raise


# _apply_appearance() / _poll_appearance() / _start_appearance_polling():
# shared live dark/light tracking, polled rather than pushed, driven by
# a per-platform detect_is_dark callable.

class _FakeGtkSettings:
    def __init__(self, prefer_dark=False):
        self._prefer_dark = prefer_dark
        self.set_calls = []

    def get_property(self, name):
        assert name == "gtk-application-prefer-dark-theme"
        return self._prefer_dark

    def set_property(self, name, value):
        assert name == "gtk-application-prefer-dark-theme"
        self._prefer_dark = value
        self.set_calls.append(value)


def test_apply_appearance_enables_dark_theme(monkeypatch):
    fake_settings = _FakeGtkSettings(prefer_dark=False)
    monkeypatch.setattr(mainview.Gtk.Settings, 'get_default', lambda: fake_settings)

    MainView._apply_appearance(None, lambda: True)

    assert fake_settings.set_calls == [True]


def test_apply_appearance_enables_light_theme(monkeypatch):
    fake_settings = _FakeGtkSettings(prefer_dark=True)
    monkeypatch.setattr(mainview.Gtk.Settings, 'get_default', lambda: fake_settings)

    MainView._apply_appearance(None, lambda: False)

    assert fake_settings.set_calls == [False]


def test_apply_appearance_skips_redundant_set(monkeypatch):
    fake_settings = _FakeGtkSettings(prefer_dark=True)
    monkeypatch.setattr(mainview.Gtk.Settings, 'get_default', lambda: fake_settings)

    MainView._apply_appearance(None, lambda: True)

    assert fake_settings.set_calls == []


def test_apply_appearance_skips_when_detection_fails(monkeypatch):
    fake_settings = _FakeGtkSettings(prefer_dark=False)
    monkeypatch.setattr(mainview.Gtk.Settings, 'get_default', lambda: fake_settings)

    MainView._apply_appearance(None, lambda: None)

    assert fake_settings.set_calls == []


def test_poll_appearance_keeps_polling():
    calls = []
    dummy = SimpleNamespace(_apply_appearance=lambda detect: calls.append(detect))
    detect_is_dark = lambda: True

    assert MainView._poll_appearance(dummy, detect_is_dark) is True
    assert calls == [detect_is_dark]


def test_start_appearance_polling_applies_immediately_and_schedules_polling(monkeypatch):
    from gi.repository import GLib
    applied = []
    dummy = SimpleNamespace(
        _apply_appearance=lambda detect: applied.append(detect),
        _poll_appearance=object())
    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add_seconds', lambda seconds, func, *args: scheduled.append((seconds, func, args)))
    detect_is_dark = lambda: True

    MainView._start_appearance_polling(dummy, detect_is_dark)

    assert applied == [detect_is_dark]
    assert scheduled == [(2, dummy._poll_appearance, (detect_is_dark,))]


# _detect_macos_is_dark() #

def test_detect_macos_is_dark_true(monkeypatch):
    monkeypatch.setattr(mainview.subprocess, 'run',
        lambda *a, **k: SimpleNamespace(stdout=b"Dark\n"))

    assert MainView._detect_macos_is_dark(None) is True


def test_detect_macos_is_dark_false_when_key_absent(monkeypatch):
    # macOS only sets AppleInterfaceStyle at all when Dark is active -
    # `defaults read` prints nothing to stdout (its error goes to
    # stderr) when the key doesn't exist, i.e. Light/Auto.
    monkeypatch.setattr(mainview.subprocess, 'run',
        lambda *a, **k: SimpleNamespace(stdout=b""))

    assert MainView._detect_macos_is_dark(None) is False


def test_detect_macos_is_dark_returns_none_on_subprocess_error(monkeypatch):
    def _raise(*a, **k):
        raise OSError('no such command')
    monkeypatch.setattr(mainview.subprocess, 'run', _raise)

    assert MainView._detect_macos_is_dark(None) is None


# _detect_windows_is_dark() #

def _fake_winreg(monkeypatch, apps_use_light_theme):
    fake_key = object()
    fake_module = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=lambda hive, path: fake_key,
        QueryValueEx=lambda key, name: (apps_use_light_theme, 1),
        CloseKey=lambda key: None,
    )
    monkeypatch.setitem(sys.modules, 'winreg', fake_module)
    return fake_module


def test_detect_windows_is_dark_true(monkeypatch):
    _fake_winreg(monkeypatch, apps_use_light_theme=0)

    assert MainView._detect_windows_is_dark(None) is True


def test_detect_windows_is_dark_false(monkeypatch):
    _fake_winreg(monkeypatch, apps_use_light_theme=1)

    assert MainView._detect_windows_is_dark(None) is False


def test_detect_windows_is_dark_returns_none_on_missing_registry_key(monkeypatch):
    def _raise(hive, path):
        raise OSError('registry key not found')
    fake_module = SimpleNamespace(HKEY_CURRENT_USER=object(), OpenKey=_raise)
    monkeypatch.setitem(sys.modules, 'winreg', fake_module)

    assert MainView._detect_windows_is_dark(None) is None


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


@pytest.mark.parametrize('is_mac, mods', [
    (True, Gdk.ModifierType.META_MASK | Gdk.ModifierType.MOD2_MASK | Gdk.ModifierType.SHIFT_MASK),
    (False, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK),
])
def test_setup_key_bindings_registers_save_as(monkeypatch, is_mac, mods):
    monkeypatch.setattr(platform, 'is_mac', is_mac)
    calls = []
    monkeypatch.setattr(Gtk.AccelMap, 'add_entry', lambda path, key, mods: calls.append((path, key, mods)))
    view = _real_view_for_key_bindings()

    MainView._setup_key_bindings(view)

    assert ("<Virtaal>/File/Save As", Gdk.KEY_s, mods) in calls


@pytest.mark.parametrize('is_mac, key, mods', [
    (True, Gdk.KEY_slash, Gdk.ModifierType.META_MASK | Gdk.ModifierType.MOD2_MASK),
    (False, Gdk.KEY_question, Gdk.ModifierType.CONTROL_MASK),
])
def test_setup_key_bindings_registers_keyboard_shortcuts(monkeypatch, is_mac, key, mods):
    monkeypatch.setattr(platform, 'is_mac', is_mac)
    calls = []
    monkeypatch.setattr(Gtk.AccelMap, 'add_entry', lambda path, key, mods: calls.append((path, key, mods)))
    view = _real_view_for_key_bindings()

    MainView._setup_key_bindings(view)

    assert ("<Virtaal>/Help/Shortcuts", key, mods) in calls


def test_setup_osx_help_menu_gives_osxapp_the_help_menu_item(monkeypatch):
    view = SimpleNamespace(gui=SimpleNamespace(get_object=lambda name: name))
    calls = []
    osxapp = SimpleNamespace(set_help_menu=lambda item: calls.append(item))
    monkeypatch.setattr(mainview, '_set_native_help_menu', lambda: calls.append('native'))

    MainView._setup_osx_help_menu(view, osxapp)

    assert calls == ["menuitem_help", "native"]


def _fake_objc(monkeypatch, objects):
    """objects maps (receiver, selector) to the reply; calls records
    every message sent."""
    calls = []

    def send(receiver, selector, *args, argtypes=None, restype=None):
        calls.append((receiver, selector) + args)
        return objects.get((receiver, selector))

    monkeypatch.setattr(mainview, '_objc_send', send)
    monkeypatch.setattr(mainview, '_objc_class', lambda name: name)
    monkeypatch.setattr(mainview, '_objc_sel', lambda name: 'sel:' + name)
    return calls


_GTKOSX_MENUBAR = {
    ('NSApplication', 'sharedApplication'): 'nsapp',
    ('nsapp', 'mainMenu'): 'menubar',
    ('menubar', 'respondsToSelector:'): True,
    ('menubar', 'helpMenu'): 'help item',
    ('help item', 'submenu'): 'help menu',
}


def test_set_native_help_menu_designates_the_help_items_submenu(monkeypatch):
    calls = _fake_objc(monkeypatch, _GTKOSX_MENUBAR)

    mainview._set_native_help_menu()

    assert ('nsapp', 'setHelpMenu:', 'help menu') in calls


@pytest.mark.parametrize('missing', [
    ('nsapp', 'mainMenu'),
    ('menubar', 'respondsToSelector:'),
    ('menubar', 'helpMenu'),
    ('help item', 'submenu'),
], ids=['no menubar', 'not gtk-mac-integration', 'no help item', 'no submenu'])
def test_set_native_help_menu_leaves_appkit_alone_without_a_help_menu(monkeypatch, missing):
    calls = _fake_objc(monkeypatch, {k: v for k, v in _GTKOSX_MENUBAR.items() if k != missing})

    mainview._set_native_help_menu()

    assert not [c for c in calls if c[1] == 'setHelpMenu:']


def test_note_recent_document_hands_appkit_a_file_url(monkeypatch):
    calls = _fake_objc(monkeypatch, {
        ('NSString', 'stringWithUTF8String:'): 'nsstring',
        ('NSURL', 'fileURLWithPath:'): 'url',
        ('NSDocumentController', 'sharedDocumentController'): 'controller',
    })

    mainview._note_recent_document('/tmp/af.po')

    assert calls[0] == ('NSString', 'stringWithUTF8String:', b'/tmp/af.po')
    assert calls[-1] == ('controller', 'noteNewRecentDocumentURL:', 'url')


@pytest.mark.skipif(not platform.is_mac, reason="the Objective-C runtime is macOS-only")
def test_objc_send_round_trips_through_the_real_runtime():
    nsstring = mainview._objc_send(mainview._objc_class("NSString"), "stringWithUTF8String:",
                                   b"Hulp", argtypes=[ctypes.c_char_p])

    assert ctypes.string_at(mainview._objc_send(nsstring, "UTF8String")) == b"Hulp"


_FRESH_PROCESS_HELP_MENU = """
import ctypes
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkosxApplication', '1.0')
from gi.repository import Gtk, GtkosxApplication
from virtaal.views import mainview
osxapp = GtkosxApplication.Application()
window = Gtk.Window()
menubar = Gtk.MenuBar()
window.add(menubar)
for title in ('Fichier', 'Aide'):
    item = Gtk.MenuItem(label=title)
    submenu = Gtk.Menu()
    submenu.append(Gtk.MenuItem(label='x'))
    item.set_submenu(submenu)
    menubar.append(item)
window.show_all()
osxapp.set_menu_bar(menubar)
osxapp.set_help_menu(menubar.get_children()[-1])
nsapp = mainview._objc_send(mainview._objc_class('NSApplication'), 'sharedApplication')
print(mainview._objc_send(nsapp, 'helpMenu'))
mainview._set_native_help_menu()
title = mainview._objc_send(mainview._objc_send(nsapp, 'helpMenu'), 'title')
print(ctypes.string_at(mainview._objc_send(title, 'UTF8String')).decode())
"""


@pytest.mark.skipif(not platform.is_mac, reason="AppKit's Help menu is macOS-only")
def test_set_native_help_menu_reaches_appkit_whatever_the_menus_title():
    # Real AppKit and gtk-mac-integration, in a fresh process so its
    # menubar can't leak into other tests.
    try:
        gi.require_version('GtkosxApplication', '1.0')
    except ValueError:
        pytest.skip('gtk-mac-integration not installed')
    import subprocess
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env = dict(os.environ, PYTHONPATH=repo_root)

    result = subprocess.run([sys.executable, '-c', _FRESH_PROCESS_HELP_MENU],
                            env=env, capture_output=True, text=True, check=True, timeout=60)

    # gtk-mac-integration alone never designates it.
    assert result.stdout.split() == ['None', 'Aide']


# show_template_update_notice(): dismissable "Update from Template" stats
# notice, replacing a blocking modal dialog (#3808).

class _FakeVboxMain:
    def __init__(self):
        self.packed = []

    def pack_start(self, widget, expand, fill, padding):
        self.packed.append(widget)

    def reorder_child(self, widget, position):
        pass


_BEFORE = {'translated': 1, 'fuzzy': 2, 'untranslated': 0, 'total': 3}
_AFTER = {'translated': 3, 'fuzzy': 0, 'untranslated': 1, 'total': 4}


def _view_for_template_update_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    return view, vbox


def test_show_template_update_notice_packs_a_dismissable_infobar():
    view, vbox = _view_for_template_update_notice()

    view.show_template_update_notice('File Updated', _BEFORE, _AFTER)

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.INFO
    assert infobar.get_show_close_button() is True


def test_template_stats_grid_lays_out_before_after_and_change():
    grid = MainView._template_stats_grid(_BEFORE, _AFTER)

    def text(column, row):
        return grid.get_child_at(column, row).get_text()

    assert [text(c, 0) for c in (1, 2, 3)] == ['Before', 'After', 'Change']
    assert [text(0, r) for r in (1, 2, 3, 4)] == ['Translated', 'Fuzzy', 'Untranslated', 'Total']
    assert [text(c, 1) for c in (1, 2, 3)] == ['1', '3', '+2']
    assert [text(c, 2) for c in (1, 2, 3)] == ['2', '0', '-2']
    assert [text(c, 4) for c in (1, 2, 3)] == ['3', '4', '+1']


def test_template_stats_grid_leaves_an_unchanged_count_blank():
    grid = MainView._template_stats_grid(_BEFORE, _BEFORE)

    assert grid.get_child_at(3, 1).get_text() == ''


def test_show_template_update_notice_replaces_a_previous_one():
    view, vbox = _view_for_template_update_notice()
    view.show_template_update_notice('First', _BEFORE, _AFTER)
    first = view._template_update_infobar

    view.show_template_update_notice('Second', _BEFORE, _AFTER)

    assert len(vbox.packed) == 2
    assert view._template_update_infobar is not first
    assert first.get_parent() is None  # destroyed, not just replaced in our own attribute


def test_show_template_update_notice_dismiss_clears_the_tracked_infobar():
    view, vbox = _view_for_template_update_notice()
    view.show_template_update_notice('File Updated', _BEFORE, _AFTER)
    infobar = view._template_update_infobar

    infobar.emit('response', Gtk.ResponseType.CLOSE)

    assert view._template_update_infobar is None


# show_same_lang_notice() / hide_same_lang_notice() - warn that source and
# target language are the same (#1346), replacing the old red button text.

def _view_for_same_lang_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    return view, vbox


def test_show_same_lang_notice_packs_a_dismissable_infobar():
    view, vbox = _view_for_same_lang_notice()

    view.show_same_lang_notice(lambda: None)

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.WARNING
    assert infobar.get_show_close_button() is True


def test_show_same_lang_notice_does_not_stack_a_second_one():
    view, vbox = _view_for_same_lang_notice()
    view.show_same_lang_notice(lambda: None)

    view.show_same_lang_notice(lambda: None)

    assert len(vbox.packed) == 1


def test_show_same_lang_notice_change_pair_button_runs_the_callback_without_dismissing():
    # Picking the same pair again (or cancelling) leaves the language
    # controller's source/target unchanged, so no notify_diff_langs()
    # follows - the notice has to stay up until it actually does.
    view, vbox = _view_for_same_lang_notice()
    calls = []
    view.show_same_lang_notice(lambda: calls.append('changed'))
    infobar = view._same_lang_infobar

    infobar.emit('response', Gtk.ResponseType.OK)

    assert calls == ['changed']
    assert view._same_lang_infobar is infobar


def test_show_same_lang_notice_dismiss_clears_the_tracked_infobar():
    view, vbox = _view_for_same_lang_notice()
    view.show_same_lang_notice(lambda: None)

    view._same_lang_infobar.emit('response', Gtk.ResponseType.CLOSE)

    assert view._same_lang_infobar is None


def test_hide_same_lang_notice_destroys_a_shown_notice():
    view, vbox = _view_for_same_lang_notice()
    view.show_same_lang_notice(lambda: None)
    infobar = view._same_lang_infobar

    view.hide_same_lang_notice()

    assert view._same_lang_infobar is None
    assert infobar.get_parent() is None


def test_hide_same_lang_notice_does_nothing_when_none_shown():
    view, vbox = _view_for_same_lang_notice()

    view.hide_same_lang_notice()  # must not raise


# show_read_only_notice() / hide_read_only_notice() - warn that the opened
# file can't be saved in place (#517).

def _view_for_read_only_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    return view, vbox


def test_show_read_only_notice_packs_a_dismissable_infobar():
    view, vbox = _view_for_read_only_notice()

    view.show_read_only_notice()

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.WARNING
    assert infobar.get_show_close_button() is True


def test_show_read_only_notice_does_not_stack_a_second_one():
    view, vbox = _view_for_read_only_notice()
    view.show_read_only_notice()

    view.show_read_only_notice()

    assert len(vbox.packed) == 1


def test_show_read_only_notice_save_as_button_saves_without_dismissing():
    # A cancelled/failed Save As shouldn't dismiss the warning - only a
    # real successful save does that.
    view, vbox = _view_for_read_only_notice()
    calls = []
    view.controller = SimpleNamespace(save_file=lambda force_saveas: calls.append(force_saveas))
    view.show_read_only_notice()
    infobar = view._read_only_infobar

    infobar.emit('response', Gtk.ResponseType.OK)

    assert calls == [True]
    assert view._read_only_infobar is infobar


def test_show_read_only_notice_dismiss_clears_the_tracked_infobar():
    view, vbox = _view_for_read_only_notice()
    view.show_read_only_notice()

    view._read_only_infobar.emit('response', Gtk.ResponseType.CLOSE)

    assert view._read_only_infobar is None


def test_hide_read_only_notice_destroys_a_shown_notice():
    view, vbox = _view_for_read_only_notice()
    view.show_read_only_notice()
    infobar = view._read_only_infobar

    view.hide_read_only_notice()

    assert view._read_only_infobar is None
    assert infobar.get_parent() is None


def test_hide_read_only_notice_does_nothing_when_none_shown():
    view, vbox = _view_for_read_only_notice()

    view.hide_read_only_notice()  # must not raise


# show_update_notice() - #3616's platform-specific download button

def _real_view_for_update_notice():
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    return SimpleNamespace(gui=builder)


def _emit_response(view, response_id):
    vbox_main = view.gui.get_object('vbox_main')
    infobar = next(c for c in vbox_main.get_children() if isinstance(c, Gtk.InfoBar))
    infobar.emit('response', response_id)
    vbox_main.remove(infobar)


def test_show_update_notice_without_asset_url_downloads_the_release_page(monkeypatch):
    from virtaal.support import openmailto
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    view = _real_view_for_update_notice()

    MainView.show_update_notice(view, 'v1.0.0', 'https://github.com/translate/virtaal/releases/tag/v1.0.0')

    _emit_response(view, Gtk.ResponseType.OK)
    assert opened == ['https://github.com/translate/virtaal/releases/tag/v1.0.0']


def test_show_update_notice_with_asset_url_download_button_opens_the_asset(monkeypatch):
    from virtaal.support import openmailto
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    view = _real_view_for_update_notice()

    MainView.show_update_notice(
        view, 'v1.0.0', 'https://github.com/translate/virtaal/releases/tag/v1.0.0',
        asset_url='https://github.com/translate/virtaal/releases/download/v1.0.0/virtaal-1.0.0-setup.exe')

    _emit_response(view, Gtk.ResponseType.OK)
    assert opened == ['https://github.com/translate/virtaal/releases/download/v1.0.0/virtaal-1.0.0-setup.exe']


def test_show_update_notice_with_asset_url_release_notes_button_opens_the_release_page(monkeypatch):
    from virtaal.support import openmailto
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    view = _real_view_for_update_notice()

    MainView.show_update_notice(
        view, 'v1.0.0', 'https://github.com/translate/virtaal/releases/tag/v1.0.0',
        asset_url='https://github.com/translate/virtaal/releases/download/v1.0.0/virtaal-1.0.0-setup.exe')

    _emit_response(view, Gtk.ResponseType.HELP)
    assert opened == ['https://github.com/translate/virtaal/releases/tag/v1.0.0']


# _open_recent_item() / _on_recent_file_activated() #

class _FakeRecentInfo:
    def __init__(self, uri, exists=True):
        self._uri = uri
        self._exists = exists

    def get_uri(self):
        return self._uri

    def get_uri_display(self):
        return self._uri.removeprefix('file://')

    def exists(self):
        return self._exists


def test_open_recent_item_opens_an_existing_file():
    opened = []
    view = SimpleNamespace(controller=SimpleNamespace(open_file=lambda display, uri: opened.append((display, uri))))

    MainView._open_recent_item(view, _FakeRecentInfo('file:///tmp/document.po'))

    assert opened == [('/tmp/document.po', 'file:///tmp/document.po')]
    assert view._uri == 'file:///tmp/document.po'


def test_open_recent_item_skips_a_missing_file():
    view = SimpleNamespace(controller=SimpleNamespace(
        open_file=lambda display, uri: pytest.fail('should not open a file that no longer exists')))

    MainView._open_recent_item(view, _FakeRecentInfo('file:///tmp/gone.po', exists=False))  # must not raise


def test_on_recent_file_activated_delegates_to_open_recent_item():
    item = _FakeRecentInfo('file:///tmp/document.po')
    opened = []
    view = SimpleNamespace(_open_recent_item=lambda i: opened.append(i))

    MainView._on_recent_file_activated(view, SimpleNamespace(get_current_item=lambda: item))

    assert opened == [item]


# _on_store_loaded()'s macOS hook: _note_recent_document() #

def test_on_store_loaded_notes_the_bundle_filename_on_mac(monkeypatch):
    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    monkeypatch.setattr(platform, 'is_mac', True)
    noted = []
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: noted.append(path))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'bundle.zip', project=True,
        get_bundle_filename=lambda: '/tmp/bundle.zip')

    view._on_store_loaded(store_controller)

    assert noted == ['/tmp/bundle.zip']


def test_on_store_loaded_notes_the_store_filename_even_with_a_dropped_uri_set(monkeypatch):
    # store_controller.store.filename, not self._uri: some open_file()
    # callers (the welcome screen's recent-files list, the macOS Dock's
    # own openFile: event) never set self._uri, leaving it stale from
    # whatever a *different*, earlier open last set it to - it must
    # never be trusted here even when it happens to be set.
    import os

    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    monkeypatch.setattr(platform, 'is_mac', True)
    noted = []
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: noted.append(path))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    view._uri = 'file:///tmp/stale-from-an-earlier-open.po'
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'dropped.po', project=None,
        store=SimpleNamespace(filename='/tmp/dropped.po'))

    view._on_store_loaded(store_controller)

    assert noted == [os.path.abspath('/tmp/dropped.po')]


def test_on_store_loaded_notes_the_plain_filename_on_mac(monkeypatch):
    import os

    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    monkeypatch.setattr(platform, 'is_mac', True)
    noted = []
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: noted.append(path))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'opened.po', project=None,
        store=SimpleNamespace(filename='/tmp/opened.po'))

    view._on_store_loaded(store_controller)

    assert noted == [os.path.abspath('/tmp/opened.po')]


def test_on_store_loaded_skips_noting_a_document_off_mac(monkeypatch):
    from virtaal.views import recent
    monkeypatch.setattr(recent, 'rm', SimpleNamespace(add_item=lambda uri: None))
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(mainview, '_note_recent_document', lambda path: pytest.fail('mac-only call'))
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: _FakeSensitiveWidget())
    view.status_bar = _FakeSensitiveWidget()
    store_controller = SimpleNamespace(
        get_store_filename=lambda: 'opened.po', project=None,
        store=SimpleNamespace(filename='/tmp/opened.po'))

    view._on_store_loaded(store_controller)  # must not raise


# fill_dialog() #

class _FakeDialogForFill:
    def __init__(self):
        self.title = None
        self.markup = None

    def set_title(self, title):
        self.title = title

    def set_markup(self, markup):
        self.markup = markup


def test_fill_dialog_sets_the_title_when_given():
    dialog = _FakeDialogForFill()
    mainview.fill_dialog(dialog, title='A Title')
    assert dialog.title == 'A Title'


def test_fill_dialog_leaves_the_title_unset_without_one():
    dialog = _FakeDialogForFill()
    mainview.fill_dialog(dialog)
    assert dialog.title is None


def test_fill_dialog_prefers_markup_over_a_plain_message():
    dialog = _FakeDialogForFill()
    mainview.fill_dialog(dialog, message='ignored', markup='<b>bold</b>')
    assert dialog.markup == '<b>bold</b>'


def test_fill_dialog_escapes_a_plain_messages_angle_brackets():
    dialog = _FakeDialogForFill()
    mainview.fill_dialog(dialog, message='a < b')
    assert dialog.markup == 'a &lt; b'


# open_chooser / save_chooser - real native file-chooser construction #

def test_open_chooser_builds_a_real_native_file_chooser():
    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()

    chooser = view.open_chooser

    assert isinstance(chooser, Gtk.FileChooserNative)
    assert len(chooser.list_filters()) > 1  # "All Supported Files" + one per format + "All Files"


def test_save_chooser_builds_a_real_native_file_chooser():
    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()

    chooser = view.save_chooser

    assert isinstance(chooser, Gtk.FileChooserNative)


# show_open_dialog()/show_save_dialog()'s remaining branches #

def test_show_open_dialog_sets_a_custom_title_when_given():
    chooser = _FakeChooser(Gtk.ResponseType.CANCEL)
    view = _make_view_with_chooser('open_chooser', chooser)

    view.show_open_dialog(title='Pick a file')

    assert chooser.title == 'Pick a file'


def test_show_save_dialog_falls_back_to_the_open_stores_filename():
    view = _make_view_with_chooser('save_chooser', _FakeChooser(Gtk.ResponseType.CANCEL))
    view.controller = SimpleNamespace(get_store=lambda: SimpleNamespace(get_filename=lambda: '/tmp/fallback.po'))

    assert view.show_save_dialog('Save') is None


# show_save_confirm_dialog()'s discard/cancel branches (the 'save'
# branch is already covered above, #3525) #

class _FakeConfirmDialogWithResponse(_FakeConfirmDialog):
    def __init__(self, response):
        super().__init__()
        self._response = response

    def run(self):
        return self._response


def test_show_save_confirm_dialog_returns_discard_on_the_discard_response(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    view.confirm_dialog = _FakeConfirmDialogWithResponse(Gtk.ResponseType.NO)
    view._top_window = _FakeTopWindow()

    assert view.show_save_confirm_dialog() == 'discard'


def test_show_save_confirm_dialog_returns_cancel_on_any_other_response(monkeypatch):
    from gi.repository import GLib
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
    view = MainView.__new__(MainView)
    view.confirm_dialog = _FakeConfirmDialogWithResponse(Gtk.ResponseType.CANCEL)
    view._top_window = _FakeTopWindow()

    assert view.show_save_confirm_dialog() == 'cancel'


# ask_plural_info() #

def test_ask_plural_info_returns_the_languages_own_plural_info_when_defined(monkeypatch):
    from translate.lang import factory as langfactory
    lang = SimpleNamespace(nplurals=2, pluralequation='(n != 1)')
    monkeypatch.setattr(langfactory, 'getlanguage', lambda code: lang)
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(lang_controller=SimpleNamespace(target_lang=SimpleNamespace(code='af')))

    assert view.ask_plural_info() == (2, '(n != 1)')


def test_ask_plural_info_prompts_for_an_equation_when_the_default_is_a_placeholder(monkeypatch):
    # nplurals > 1 with the "0" placeholder equation means the language
    # database doesn't actually know this language's real rule.
    from translate.lang import factory as langfactory
    lang = SimpleNamespace(nplurals=3, pluralequation='0')
    monkeypatch.setattr(langfactory, 'getlanguage', lambda code: lang)
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(lang_controller=SimpleNamespace(target_lang=SimpleNamespace(code='ar')))
    view.show_input_dialog = lambda message: 'n % 100 == 1 ? 0 : 1'

    assert view.ask_plural_info() == (3, 'n % 100 == 1 ? 0 : 1')


def test_ask_plural_info_prompts_for_a_plural_count_when_the_language_has_none(monkeypatch):
    from translate.lang import factory as langfactory
    lang = SimpleNamespace(nplurals=0, pluralequation='0')
    monkeypatch.setattr(langfactory, 'getlanguage', lambda code: lang)
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(lang_controller=SimpleNamespace(target_lang=SimpleNamespace(code='xx')))
    prompts = iter(['not a number', '1'])
    view.show_input_dialog = lambda message: next(prompts)

    assert view.ask_plural_info() == (1, '0')


# append_menu_item() #

def _menu_with_item(label):
    menu = Gtk.Menu()
    item = Gtk.MenuItem(label=label)
    menu.append(item)
    parent_item = Gtk.MenuItem(label='Parent')
    parent_item.set_submenu(menu)
    return parent_item, menu, item


def test_append_menu_item_adds_to_the_end_by_default():
    view = MainView.__new__(MainView)
    parent_item, menu, existing = _menu_with_item('Existing')

    new_item = view.append_menu_item('New', parent_item)

    assert menu.get_children() == [existing, new_item]
    assert new_item.get_visible() is True


def test_append_menu_item_inserts_after_a_given_item():
    view = MainView.__new__(MainView)
    parent_item, menu, existing = _menu_with_item('Existing')
    trailing = Gtk.MenuItem(label='Trailing')
    menu.append(trailing)

    new_item = view.append_menu_item('New', parent_item, after=existing)

    assert menu.get_children() == [existing, new_item, trailing]


def test_append_menu_item_resolves_a_string_menu_name():
    view = MainView.__new__(MainView)
    parent_item, menu, existing = _menu_with_item('Existing')
    view.find_menu = lambda label: parent_item if label == 'File' else None

    new_item = view.append_menu_item('New', 'File')

    assert menu.get_children() == [existing, new_item]


def test_append_menu_item_returns_none_when_the_target_menu_is_missing():
    view = MainView.__new__(MainView)
    view.find_menu = lambda label: None

    assert view.append_menu_item('New', 'Missing') is None


def test_append_menu_item_resolves_a_string_after_label():
    view = MainView.__new__(MainView)
    parent_item, menu, existing = _menu_with_item('Existing')
    view.find_menu = lambda label: existing if label == 'Existing' else None

    new_item = view.append_menu_item('New', parent_item, after='Existing')

    assert menu.get_children() == [existing, new_item]


# _setup_windows_integration() / _setup_recent_files() - both only
# ever run for real via a GLib scheduling call this suite never pumps #

def test_setup_windows_integration_polls_the_windows_dark_mode_detector(monkeypatch):
    from gi.repository import GLib
    scheduled = []
    monkeypatch.setattr(GLib, 'timeout_add_seconds', lambda seconds, cb, *a: scheduled.append((seconds, cb, a)))
    view = MainView.__new__(MainView)
    applied = []
    view._apply_appearance = applied.append

    view._setup_windows_integration()

    assert applied == [view._detect_windows_is_dark]
    assert scheduled == [(2, view._poll_appearance, (view._detect_windows_is_dark,))]


def test_setup_recent_files_wires_the_recent_chooser_into_its_menu(monkeypatch):
    from virtaal.views import recent
    fake_rc = SimpleNamespace(connect=lambda signal, handler: None)
    monkeypatch.setattr(recent, 'rc', fake_rc)
    view = MainView.__new__(MainView)
    submenus = []
    recent_files_menu = SimpleNamespace(set_submenu=submenus.append)
    view.gui = SimpleNamespace(get_object=lambda name: recent_files_menu)

    view._setup_recent_files()

    assert submenus == [fake_rc]


# _on_osx_openfile_event() - GtkosxApplication's own "open this file"
# signal; deferred via idle_add since GTK's own run-loop can't be
# touched from inside this handler (gdk/quartz/gdkeventloop-quartz.c) #

def test_on_osx_openfile_event_defers_opening_via_idle_add(monkeypatch):
    from gi.repository import GLib
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', scheduled.append)
    opened = []
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(open_file=lambda filename: opened.append(filename))

    result = view._on_osx_openfile_event(None, 'dropped.po')

    assert result is True
    assert len(scheduled) == 1
    scheduled[0]()
    assert opened == ['dropped.po']


# _on_drag_data_received() - dropping a file onto the main window #

def test_on_drag_data_received_opens_a_decoded_file_uri(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(Gtk, 'targets_include_uri', lambda targets: True)
    view = MainView.__new__(MainView)
    opened = []
    view.controller = SimpleNamespace(
        open_file=lambda filename: opened.append(filename),
        show_error=lambda msg: pytest.fail('must not show an error for a valid drop'))
    context = SimpleNamespace(list_targets=lambda: ['text/uri-list'])
    data = SimpleNamespace(get_data=lambda: b'file:///tmp/dropped.po\r\n')

    result = view._on_drag_data_received(None, context, 0, 0, data, 0, 0)

    assert result is True
    assert opened == ['file:///tmp/dropped.po']


def test_on_drag_data_received_shows_an_error_for_undecodable_bytes(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(Gtk, 'targets_include_uri', lambda targets: True)
    view = MainView.__new__(MainView)
    errors = []
    view.controller = SimpleNamespace(
        show_error=lambda msg: errors.append(msg),
        open_file=lambda *a: pytest.fail('must not open an undecodable drop'))
    context = SimpleNamespace(list_targets=lambda: ['text/uri-list'])
    data = SimpleNamespace(get_data=lambda: b'\xff\xfe not utf-8\r\n')

    view._on_drag_data_received(None, context, 0, 0, data, 0, 0)

    assert len(errors) == 1


def test_on_drag_data_received_ignores_a_non_file_drop(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(Gtk, 'targets_include_uri', lambda targets: True)
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(
        open_file=lambda *a: pytest.fail('must not open a non-file:// drop'),
        show_error=lambda *a: pytest.fail('must not show an error for a non-URI drop'))
    context = SimpleNamespace(list_targets=lambda: ['text/uri-list'])
    data = SimpleNamespace(get_data=lambda: b'not-a-uri\r\n')

    view._on_drag_data_received(None, context, 0, 0, data, 0, 0)  # must not raise


def test_on_drag_data_received_ignores_unsupported_targets(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(Gtk, 'targets_include_uri', lambda targets: False)
    view = MainView.__new__(MainView)
    view.controller = SimpleNamespace(open_file=lambda *a: pytest.fail('must not open with unsupported targets'))
    context = SimpleNamespace(list_targets=lambda: [])
    data = SimpleNamespace(get_data=lambda: b'file:///tmp/dropped.po\r\n')

    assert view._on_drag_data_received(None, context, 0, 0, data, 0, 0) is True


# _on_style_set()'s Windows-only tooltip-contrast provider (bug 1923) #

def test_on_style_set_adds_a_tooltip_colour_provider_on_windows(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr(mainview.theme, 'update_style', lambda w: None)
    monkeypatch.setattr(mainview.theme, 'INVERSE', False)
    view = MainView.__new__(MainView)
    view._tooltip_fg_provider = None
    widget = Gtk.Entry()

    view._on_style_set(widget)

    assert view._tooltip_fg_provider is not None


def test_on_style_set_replaces_a_previous_tooltip_provider(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr(mainview.theme, 'update_style', lambda w: None)
    monkeypatch.setattr(mainview.theme, 'INVERSE', True)
    view = MainView.__new__(MainView)
    view._tooltip_fg_provider = None
    widget = Gtk.Entry()
    view._on_style_set(widget)
    first_provider = view._tooltip_fg_provider

    view._on_style_set(widget)

    assert view._tooltip_fg_provider is not first_provider


def test_on_style_set_leaves_no_tooltip_provider_off_windows(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    monkeypatch.setattr(mainview.theme, 'update_style', lambda w: None)
    view = MainView.__new__(MainView)
    view._tooltip_fg_provider = None
    widget = Gtk.Entry()

    view._on_style_set(widget)

    assert view._tooltip_fg_provider is None


# open_file() / hide() / show() #

def test_open_file_opens_the_chosen_file_and_records_its_uri():
    opened = []
    view = MainView.__new__(MainView)
    view.show_open_dialog = lambda: ('chosen.po', 'file:///chosen.po')
    view.controller = SimpleNamespace(open_file=lambda filename, uri=None: opened.append((filename, uri)))

    view.open_file()

    assert opened == [('chosen.po', 'file:///chosen.po')]
    assert view._uri == 'file:///chosen.po'


def test_open_file_returns_false_when_the_chooser_is_cancelled():
    view = MainView.__new__(MainView)
    view.show_open_dialog = lambda: ()
    view.controller = SimpleNamespace(open_file=lambda *a, **k: pytest.fail('must not open anything'))

    assert view.open_file() is False


def test_hide_captures_geometry_then_hides_and_pumps_pending_events(monkeypatch):
    # Never pump the *real* main loop in a test - depending on what's
    # left over from the rest of the suite's own real GTK objects,
    # Gtk.main_iteration() can process a pending event that itself
    # blocks (e.g. a nested dialog), hanging the whole run.
    monkeypatch.setattr(Gtk, 'events_pending', lambda: False)
    calls = []
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(
        get_size=lambda: (640, 480),
        get_position=lambda: (1, 2),
        hide=lambda: calls.append('hide'),
    )

    view.hide()

    assert calls == ['hide']
    assert view._pre_hide_size == (640, 480)
    assert view._pre_hide_position == (1, 2)


def test_show_maximizes_when_previously_maximized(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'general', {'maximized': 1})
    monkeypatch.setattr(Gtk, 'main', lambda: None)
    view = MainView.__new__(MainView)
    calls = []
    view.main_window = SimpleNamespace(maximize=lambda: calls.append('maximize'), show=lambda: calls.append('show'))

    view.show()

    assert calls == ['maximize', 'show']


def test_show_does_not_maximize_when_not_previously_maximized(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'general', {'maximized': ''})
    monkeypatch.setattr(Gtk, 'main', lambda: None)
    view = MainView.__new__(MainView)
    calls = []
    view.main_window = SimpleNamespace(maximize=lambda: calls.append('maximize'), show=lambda: calls.append('show'))

    view.show()

    assert calls == ['show']


# show_config_recovery_notice() / show_language_change_notice() -
# same dismissable-InfoBar pattern as show_template_update_notice() #

def test_show_config_recovery_notice_packs_a_warning_infobar():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)

    view.show_config_recovery_notice('/tmp/virtaal.ini.bak')

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.WARNING


def test_show_config_recovery_notice_dismisses_on_response():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_config_recovery_notice('/tmp/virtaal.ini.bak')
    infobar = vbox.packed[0]

    infobar.emit('response', Gtk.ResponseType.CLOSE)  # must not raise

    assert infobar.get_parent() is None


# show_loading_notice() / hide_loading_notice() - a lightweight status
# label shown while main.py's deferred startup-file open is in progress #

def test_show_loading_notice_packs_a_centered_label():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)

    view.show_loading_notice('some.po')

    assert len(vbox.packed) == 1
    label = vbox.packed[0]
    assert isinstance(label, Gtk.Label)
    assert "some.po" in label.get_text()
    assert label.get_halign() == Gtk.Align.CENTER
    assert label.get_valign() == Gtk.Align.CENTER


def test_show_loading_notice_does_not_stack_a_second_one():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_loading_notice('some.po')

    view.show_loading_notice('other.po')

    assert len(vbox.packed) == 1


def test_hide_loading_notice_destroys_a_shown_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_loading_notice('some.po')
    label = view._loading_label

    view.hide_loading_notice()

    assert view._loading_label is None
    assert label.get_parent() is None


def test_hide_loading_notice_does_nothing_when_none_shown():
    view = MainView.__new__(MainView)

    view.hide_loading_notice()  # must not raise


# show_startup_open_failure_notice() - same dismissable-InfoBar pattern
# as show_config_recovery_notice(), shown alongside the modal error
# dialog after a failed startup-file open #

def test_show_startup_open_failure_notice_includes_the_reason_when_given():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)

    view.show_startup_open_failure_notice('missing.po', 'The file does not exist.')

    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.WARNING
    label = infobar.get_content_area().get_children()[0]
    assert label.get_text() == "Couldn't open 'missing.po': The file does not exist."


def test_show_startup_open_failure_notice_falls_back_without_a_reason():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)

    view.show_startup_open_failure_notice('missing.po', None)

    label = vbox.packed[0].get_content_area().get_children()[0]
    assert label.get_text() == "Couldn't open 'missing.po'."


def test_show_startup_open_failure_notice_dismisses_on_response():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_startup_open_failure_notice('missing.po', 'gone')
    infobar = vbox.packed[0]

    infobar.emit('response', Gtk.ResponseType.CLOSE)  # must not raise

    assert infobar.get_parent() is None


def test_hide_startup_open_failure_notice_destroys_a_shown_notice():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_startup_open_failure_notice('missing.po', 'gone')
    infobar = vbox.packed[0]

    view.hide_startup_open_failure_notice()

    assert infobar.get_parent() is None


def test_hide_startup_open_failure_notice_does_nothing_when_none_shown():
    view = MainView.__new__(MainView)

    view.hide_startup_open_failure_notice()  # must not raise


def test_show_language_change_notice_packs_an_info_infobar():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)

    view.show_language_change_notice()

    assert len(vbox.packed) == 1
    infobar = vbox.packed[0]
    assert isinstance(infobar, Gtk.InfoBar)
    assert infobar.get_message_type() == Gtk.MessageType.INFO


def test_show_language_change_notice_does_not_stack_a_second_one():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_language_change_notice()

    view.show_language_change_notice()

    assert len(vbox.packed) == 1


def test_show_language_change_notice_dismiss_clears_the_tracked_infobar():
    vbox = _FakeVboxMain()
    view = MainView.__new__(MainView)
    view.gui = SimpleNamespace(get_object=lambda name: vbox)
    view.show_language_change_notice()

    view._language_change_infobar.emit('response', Gtk.ResponseType.CLOSE)

    assert view._language_change_infobar is None


def test_set_statusbar_message_clears_with_an_empty_message():
    calls = []
    view = MainView.__new__(MainView)
    view.status_bar = SimpleNamespace(
        pop=lambda ctx: calls.append(('pop', ctx)),
        push=lambda ctx, msg: calls.append(('push', ctx, msg)),
    )
    view.statusbar_context_id = 7

    view.set_statusbar_message('')

    assert calls == [('pop', 7), ('push', 7, '')]


def test_set_statusbar_message_pushes_a_non_empty_message():
    calls = []
    view = MainView.__new__(MainView)
    view.status_bar = SimpleNamespace(
        pop=lambda ctx: calls.append(('pop', ctx)),
        push=lambda ctx, msg: calls.append(('push', ctx, msg)),
    )
    view.statusbar_context_id = 7

    view.set_statusbar_message('wrapped around')

    assert calls == [('pop', 7), ('push', 7, 'wrapped around')]


# _on_fullscreen() - show_app_icon()/hide_app_icon() are stubbed out:
# both use Gtk.Widget.reparent(), a real deprecated GTK call with no
# replacement short of rebuilding the menu bar, out of scope here #

def test_on_fullscreen_enters_fullscreen_and_shows_the_app_icon(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    calls = []
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(
        fullscreen=lambda: calls.append('fullscreen'), unfullscreen=lambda: calls.append('unfullscreen'))
    view.status_bar = SimpleNamespace(hide=lambda: calls.append('status-hide'), show=lambda: calls.append('status-show'))
    view.menubar = SimpleNamespace(hide=lambda: calls.append('menubar-hide'), show=lambda: calls.append('menubar-show'))
    view.show_app_icon = lambda: calls.append('show-app-icon')
    view.hide_app_icon = lambda: calls.append('hide-app-icon')

    view._on_fullscreen(SimpleNamespace(get_active=lambda: True))

    assert calls == ['fullscreen', 'status-hide', 'show-app-icon', 'menubar-hide']


def test_on_fullscreen_leaves_fullscreen_and_hides_the_app_icon(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    calls = []
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(
        fullscreen=lambda: calls.append('fullscreen'), unfullscreen=lambda: calls.append('unfullscreen'))
    view.status_bar = SimpleNamespace(hide=lambda: calls.append('status-hide'), show=lambda: calls.append('status-show'))
    view.menubar = SimpleNamespace(hide=lambda: calls.append('menubar-hide'), show=lambda: calls.append('menubar-show'))
    view.show_app_icon = lambda: calls.append('show-app-icon')
    view.hide_app_icon = lambda: calls.append('hide-app-icon')

    view._on_fullscreen(SimpleNamespace(get_active=lambda: False))

    assert calls == ['unfullscreen', 'status-show', 'hide-app-icon', 'menubar-show']



@pytest.mark.parametrize('active, expected', [(True, ['fullscreen']), (False, ['unfullscreen'])])
def test_on_fullscreen_on_macos_leaves_the_menu_bar_alone(monkeypatch, active, expected):
    monkeypatch.setattr(platform, 'is_mac', True)
    calls = []
    view = MainView.__new__(MainView)
    view.main_window = SimpleNamespace(
        fullscreen=lambda: calls.append('fullscreen'), unfullscreen=lambda: calls.append('unfullscreen'))
    view.status_bar = SimpleNamespace(hide=lambda: calls.append('status-hide'), show=lambda: calls.append('status-show'))
    view.menubar = SimpleNamespace(hide=lambda: calls.append('menubar-hide'), show=lambda: calls.append('menubar-show'))
    view.show_app_icon = lambda: calls.append('show-app-icon')
    view.hide_app_icon = lambda: calls.append('hide-app-icon')

    view._on_fullscreen(SimpleNamespace(get_active=lambda: active))

    assert calls == expected

# trivial menu/signal delegators #

def test_on_file_open_delegates_to_open_file():
    view = MainView.__new__(MainView)
    calls = []
    view.open_file = lambda: calls.append('opened')

    view._on_file_open(None)

    assert calls == ['opened']


def test_on_file_save_delegates_to_the_controller():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(save_file=lambda: calls.append('saved'))

    view._on_file_save()

    assert calls == ['saved']


def test_on_file_saveas_forces_the_saveas_dialog():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(save_file=lambda force_saveas: calls.append(force_saveas))

    view._on_file_saveas()

    assert calls == [True]


def test_on_file_binary_export_delegates_to_the_controller():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(binary_export=lambda: calls.append('exported'))

    view._on_file_binary_export()

    assert calls == ['exported']


def test_on_file_close_delegates_to_the_controller():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(close_file=lambda: calls.append('closed'))

    view._on_file_close()

    assert calls == ['closed']


def test_on_file_update_opens_a_template_and_updates_the_current_file():
    view = MainView.__new__(MainView)
    view.template_chooser = object()
    view.show_open_dialog = lambda chooser: ('template.pot', 'file:///template.pot')
    calls = []
    view.controller = SimpleNamespace(update_file=lambda filename, uri=None: calls.append((filename, uri)))

    view._on_file_update(None)

    assert calls == [('template.pot', 'file:///template.pot')]
    assert view._uri == 'file:///template.pot'


def test_on_file_update_does_nothing_when_the_chooser_is_cancelled():
    view = MainView.__new__(MainView)
    view.template_chooser = object()
    view.show_open_dialog = lambda chooser: ()
    view.controller = SimpleNamespace(update_file=lambda *a, **k: pytest.fail('must not update anything'))

    view._on_file_update(None)  # must not raise


def test_on_file_revert_delegates_to_the_controller():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(revert_file=lambda: calls.append('reverted'))

    view._on_file_revert()

    assert calls == ['reverted']


def test_on_tutorial_delegates_to_the_controller():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(open_tutorial=lambda: calls.append('opened'))

    view._on_tutorial()

    assert calls == ['opened']


def test_on_quit_delegates_to_the_controller_and_swallows_the_event():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(quit=lambda: calls.append('quit'))

    assert view._on_quit() is True
    assert calls == ['quit']


def test_on_next_unit_advances_the_unit_view():
    view = MainView.__new__(MainView)
    calls = []
    view.controller = SimpleNamespace(unit_controller=SimpleNamespace(
        view=SimpleNamespace(finish_editing_and_advance=lambda: calls.append('advanced'))))

    view._on_next_unit()

    assert calls == ['advanced']


def test_on_state_advance_advances_the_workflow_state_forward():
    view = MainView.__new__(MainView)
    calls = []
    unit_view = SimpleNamespace(
        advance_workflow_state=lambda offset: calls.append(('advance', offset)),
        finish_editing_and_advance=lambda: calls.append('advanced'),
    )
    view.controller = SimpleNamespace(unit_controller=SimpleNamespace(view=unit_view))

    view._on_state_advance()

    assert calls == [('advance', 1), 'advanced']


def test_on_state_reverse_advances_the_workflow_state_backward():
    view = MainView.__new__(MainView)
    calls = []
    unit_view = SimpleNamespace(
        advance_workflow_state=lambda offset: calls.append(('advance', offset)),
        finish_editing_and_advance=lambda: calls.append('advanced'),
    )
    view.controller = SimpleNamespace(unit_controller=SimpleNamespace(view=unit_view))

    view._on_state_reverse()

    assert calls == [('advance', -1), 'advanced']


def test_on_documentation_opens_the_docs_url(monkeypatch):
    from virtaal.support import openmailto
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    view = MainView.__new__(MainView)

    view._on_documentation()

    assert opened == ['https://docs.translatehouse.org/projects/virtaal/en/latest/using_virtaal.html']


def test_on_localization_guide_opens_the_guide_url(monkeypatch):
    from virtaal.support import openmailto
    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    view = MainView.__new__(MainView)

    view._on_localization_guide()

    assert opened == ['https://docs.translatehouse.org/projects/localization-guide/en/']


def test_on_help_about_shows_a_real_about_dialog():
    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()

    view._on_help_about()  # must not raise


def test_on_shortcuts_shows_a_real_shortcuts_window():
    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()

    view._on_shortcuts()  # must not raise


def test_macos_integration_rebinds_its_catalog_before_building_the_app_menu(monkeypatch):
    # GtkosxApplication binds its own catalogs on creation and looks up
    # the app menu's strings (Hide, Quit, ...) in set_menu_bar().
    from unittest import mock

    import gi
    from gi.repository import Gtk

    from virtaal.views import mainview

    calls = []

    class FakeApplication:
        def __init__(self):
            calls.append('Application')

        def set_menu_bar(self, menubar):
            calls.append('set_menu_bar')

        def __getattr__(self, name):
            return lambda *args: None

    monkeypatch.setattr(gi, 'require_version', lambda *args: None)
    monkeypatch.setattr(gi.repository, 'GtkosxApplication',
                        mock.Mock(Application=FakeApplication), raising=False)
    monkeypatch.setattr(mainview, 'rebind_library_domain', lambda domain: calls.append(('rebind', domain)))
    monkeypatch.setattr(Gtk.AccelMap, 'load', lambda path: None)
    view = mock.Mock()

    mainview.MainView._setup_macos_integration(view)

    assert calls[:3] == ['Application', ('rebind', b'gtk-mac-integration'), 'set_menu_bar']
