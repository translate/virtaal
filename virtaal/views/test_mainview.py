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

from urllib.parse import quote

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

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
        '_open_chooser', _FakeChooser(Gtk.ResponseType.ACCEPT))
    filename, uri = view.show_open_dialog()
    assert filename == '/tmp/test.po'


def test_show_open_dialog_returns_nothing_on_cancel():
    view = _make_view_with_chooser(
        '_open_chooser', _FakeChooser(Gtk.ResponseType.CANCEL))
    assert view.show_open_dialog() == ()


def test_show_save_dialog_returns_filename_on_accept():
    view = _make_view_with_chooser(
        '_save_chooser', _FakeChooser(Gtk.ResponseType.ACCEPT))
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


def test_show_save_dialog_returns_none_on_cancel():
    view = _make_view_with_chooser(
        '_save_chooser', _FakeChooser(Gtk.ResponseType.CANCEL))
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
