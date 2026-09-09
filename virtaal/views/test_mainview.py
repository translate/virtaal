#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Regression tests for MainView's native file dialogs.

GtkFileChooserNative (a GtkNativeDialog) returns Gtk.ResponseType.ACCEPT
on accept, never .OK - confirmed against GTK's own docs
(Gtk-3.0.gir: "will return #GTK_RESPONSE_ACCEPT if the user accepted").
show_open_dialog()/show_save_dialog() compared against .OK instead,
which is never returned by a real click - clicking Open/Save silently
did nothing, no error.
"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

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
