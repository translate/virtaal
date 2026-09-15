#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.plugins.lookup.models import weblookup
from virtaal.plugins.lookup.models.weblookup import (
    WebLookupAddDialog,
    WebLookupConfigDialog,
)
from virtaal.views import baseview


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    monkeypatch.setattr(baseview, '_builders', {})


def test_treeview_scrolled_window_is_not_focusable():
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the treeview inside it (confirmed live: Right-arrow/Down got
    # stuck, same issue as prefsview.py's plugin/placeables lists).
    dialog = WebLookupConfigDialog(parent=None)

    assert not dialog.tvw_urls.get_parent().get_can_focus()


def test_reopening_the_dialog_does_not_duplicate_columns():
    WebLookupConfigDialog(parent=None)
    dialog = WebLookupConfigDialog(parent=None)

    assert len(dialog.tvw_urls.get_columns()) == 3


def test_reopening_the_dialog_does_not_duplicate_button_handlers():
    calls = []

    class _FakeAddDialog:
        def run(self):
            calls.append('add')
            return None

    first = WebLookupConfigDialog(parent=None)
    first.add_dialog = _FakeAddDialog()
    second = WebLookupConfigDialog(parent=None)
    second.add_dialog = _FakeAddDialog()

    second.btn_url_add.clicked()

    assert len(calls) == 1


def test_every_instance_shares_the_same_url_list():
    first = WebLookupConfigDialog(parent=None)
    second = WebLookupConfigDialog(parent=None)

    second.urldata = [{'display_name': 'Example', 'url': 'http://example.com', 'quoted': False}]

    assert first.urldata == second.urldata


def test_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(weblookup.GLib, 'idle_add', lambda func, *args: func(*args))
    dialog = WebLookupConfigDialog(parent=None)
    parent = Gtk.Window()
    calls = []
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run(parent=parent)

    assert calls == ['parent']


def test_add_dialog_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(weblookup.GLib, 'idle_add', lambda func, *args: func(*args))
    parent = Gtk.Window()
    dialog = WebLookupAddDialog(parent=parent)
    calls = []
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CANCEL)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run()

    assert calls == ['parent']
