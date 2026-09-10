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


class _FakeWidget:
    def __init__(self):
        self.sensitive = None

    def set_sensitive(self, value):
        self.sensitive = value


class _FakeGui:
    """Only get_object('vbox_main') returns something real (for the
    InfoBar packing calls) - everything else is a throwaway widget
    that just records set_sensitive()."""

    def __init__(self, vbox):
        self._vbox = vbox
        self._widgets = {}

    def get_object(self, name):
        if name == 'vbox_main':
            return self._vbox
        return self._widgets.setdefault(name, _FakeWidget())


def _make_bare_view():
    view = MainView.__new__(MainView)
    view.gui = _FakeGui(Gtk.Box())
    return view


def test_show_readonly_notice_adds_a_non_dismissible_infobar():
    view = _make_bare_view()
    view.show_readonly_notice('cannot save')
    assert view._readonly_infobar in view.gui._vbox.get_children()
    assert view._readonly_infobar.get_show_close_button() is False


def test_show_readonly_notice_replaces_rather_than_stacks():
    view = _make_bare_view()
    view.show_readonly_notice('first')
    view.show_readonly_notice('second')
    assert len(view.gui._vbox.get_children()) == 1


def test_hide_readonly_notice_removes_it():
    view = _make_bare_view()
    view.show_readonly_notice('cannot save')
    view.hide_readonly_notice()
    assert view._readonly_infobar is None
    assert view.gui._vbox.get_children() == []


def test_hide_readonly_notice_is_a_noop_without_one():
    view = _make_bare_view()
    view.hide_readonly_notice()  # must not raise


def test_set_saveable_stays_disabled_for_an_unsavable_store():
    view = _make_bare_view()
    view.modified = False
    view._store_unsavable = True
    view.controller = type('_C', (), {'get_store_filename': lambda self: None})()
    view.set_saveable(True)
    assert view.gui.get_object('mnu_save').sensitive is False
    assert view.modified is False
