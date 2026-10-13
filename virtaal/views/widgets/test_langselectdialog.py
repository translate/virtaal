#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk

from virtaal.views import baseview
from virtaal.views.widgets import langselectdialog
from virtaal.views.widgets.langselectdialog import LanguageSelectDialog


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    # A cached builder hands every test the same treeviews, with earlier
    # tests' row-activated handlers still connected.
    monkeypatch.setattr(baseview, '_builders', {})


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


def _langs(*codes):
    return [SimpleNamespace(name=code.upper(), code=code) for code in codes]


def _responses(dialog):
    responses = []
    dialog.dialog.connect('response', lambda d, response: responses.append(response))
    return responses


def test_ok_is_the_default_button():
    dialog = LanguageSelectDialog(languages=[])

    assert dialog.dialog.get_default_widget() is dialog.btn_ok


def test_activating_a_row_from_the_keyboard_accepts_the_dialog():
    dialog = LanguageSelectDialog(languages=_langs('af', 'zu'))
    responses = _responses(dialog)

    dialog.tvw_targetlang.row_activated(Gtk.TreePath(1), dialog.tvw_targetlang.get_column(0))

    assert responses == [Gtk.ResponseType.OK]


def test_double_clicking_a_row_does_not_accept_the_dialog(monkeypatch):
    # Double-clicking the source language must still leave the target to pick.
    monkeypatch.setattr(langselectdialog.Gtk, 'get_current_event',
                        lambda: Gdk.Event.new(Gdk.EventType.BUTTON_RELEASE))
    dialog = LanguageSelectDialog(languages=_langs('af', 'zu'))
    responses = _responses(dialog)

    dialog.tvw_sourcelang.row_activated(Gtk.TreePath(1), dialog.tvw_sourcelang.get_column(0))

    assert responses == []


def test_selecting_a_language_moves_the_cursor_to_it():
    # Arrow keys and Enter act on the cursor row, not the selection.
    dialog = LanguageSelectDialog(languages=_langs('af', 'nl', 'zu'))

    dialog._select_lang(dialog.tvw_sourcelang, 'zu')

    assert dialog.get_selected_source_lang() == 'zu'
    assert dialog.tvw_sourcelang.get_cursor()[0].get_indices() == [2]

