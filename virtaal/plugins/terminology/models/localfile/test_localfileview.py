#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.plugins.terminology.models.localfile.localfileview import (
    FileSelectDialog,
    TermAddDialog,
)


class _FakeEntry:
    def grab_focus(self):
        pass


class _FakeDialog:
    def __init__(self):
        self.calls = []

    def set_transient_for(self, window):
        pass

    def show(self):
        self.calls.append('show')

    def present(self):
        self.calls.append('present')

    def run(self):
        return Gtk.ResponseType.CANCEL

    def hide(self):
        pass


def test_run_shows_before_presenting():
    # present() only raises/focuses an already-realized window - on the
    # very first run() it isn't yet, so show() has to come first or the
    # dialog opens without real OS-level keyboard focus on macOS.
    add_dialog = TermAddDialog.__new__(TermAddDialog)
    add_dialog.dialog = _FakeDialog()
    add_dialog.ent_source = _FakeEntry()
    add_dialog.reset = lambda: None
    add_dialog._on_entry_changed = lambda *args: None

    add_dialog.run()

    assert add_dialog.dialog.calls == ['show', 'present']


def test_treeview_scrolled_window_is_not_focusable(monkeypatch):
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the treeview inside it (same issue as prefsview.py's
    # plugin/placeables lists and weblookup.py's URL list).
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)

    dialog = FileSelectDialog(model=SimpleNamespace(controller=None, config={'files': []}))

    assert not dialog.tvw_termfiles.get_parent().get_can_focus()
