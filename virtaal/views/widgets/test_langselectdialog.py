#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.widgets import langselectdialog
from virtaal.views.widgets.langselectdialog import LanguageSelectDialog


def test_treeview_scrolled_windows_are_not_focusable():
    # The .ui file marks these focusable, which swallows Tab/Down meant
    # for the treeview inside them (same issue as prefsview.py's
    # plugin/placeables lists and weblookup.py's URL list).
    dialog = LanguageSelectDialog(languages=[])

    assert not dialog.tvw_sourcelang.get_parent().get_can_focus()
    assert not dialog.tvw_targetlang.get_parent().get_can_focus()


def test_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(langselectdialog.GLib, 'idle_add', lambda func, *args: func(*args))
    parent = Gtk.Window()
    dialog = LanguageSelectDialog(languages=[], parent=parent)
    calls = []
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CANCEL)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run(srclang='en', tgtlang='af')

    assert calls == ['parent']
