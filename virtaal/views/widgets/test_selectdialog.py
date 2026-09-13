#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.widgets.selectdialog import SelectDialog


def test_run_presents_the_window_and_restores_the_parents_focus(monkeypatch):
    # show_all() alone doesn't request real OS-level focus on macOS -
    # confirmed live: the window opened but stayed unfocused until
    # clicked, and closing it left the parent unfocused too.
    dialog = SelectDialog()
    parent = Gtk.Window()
    dialog.set_transient_for(parent)
    calls = []
    monkeypatch.setattr(dialog.dialog, 'present', lambda: calls.append('dialog'))
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run(items=[])

    assert calls == ['dialog', 'parent']
