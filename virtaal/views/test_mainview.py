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
        get_store_filename=lambda: 'bundle.zip', project=True, _archivetemp=False,
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
        get_store_filename=lambda: 'bundle.zip', project=True, _archivetemp=False,
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
