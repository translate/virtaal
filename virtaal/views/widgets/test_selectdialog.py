#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GdkPixbuf, Gtk

from virtaal.views.widgets import selectdialog
from virtaal.views.widgets.selectdialog import SelectDialog


def test_run_presents_the_window_and_restores_the_parents_focus(monkeypatch):
    # show_all() alone doesn't request real OS-level focus on macOS: the
    # window opens unfocused, and closing it leaves the parent unfocused.
    monkeypatch.setattr(selectdialog.GLib, 'idle_add', lambda func, *args: func(*args))
    dialog = SelectDialog()
    parent = Gtk.Window()
    dialog.set_transient_for(parent)
    calls = []
    monkeypatch.setattr(dialog.dialog, 'present', lambda: calls.append('dialog'))
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run(items=[])

    assert calls == ['dialog', 'parent']


def test_scrolled_window_propagates_natural_width():
    dialog = SelectDialog()

    scrolled_window = dialog.sview.get_parent()

    assert scrolled_window.get_property('propagate-natural-width')


def _run_without_blocking(monkeypatch, dialog):
    monkeypatch.setattr(selectdialog.GLib, 'idle_add', lambda func, *args: None)
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CLOSE)


def test_size_sets_the_dialogs_size_request():
    assert SelectDialog(size=(300, 200)).dialog.get_size_request() == (300, 200)


def test_size_leaves_an_unset_dimension_natural():
    assert SelectDialog(size=(0, 200)).dialog.get_size_request() == (-1, 200)
    assert SelectDialog(size=(300, -1)).dialog.get_size_request() == (300, -1)


def test_parent_makes_the_dialog_transient_for_it():
    parent = Gtk.Window()

    dialog = SelectDialog(parent=parent)

    assert dialog.dialog.get_transient_for() is parent


def test_run_with_a_parent_makes_the_dialog_transient_for_it(monkeypatch):
    dialog = SelectDialog()
    parent = Gtk.Window()
    _run_without_blocking(monkeypatch, dialog)

    dialog.run(items=[], parent=parent)

    assert dialog.dialog.get_transient_for() is parent
    assert dialog.dialog.get_parent() is None


def test_message_round_trips():
    dialog = SelectDialog(message='Pick one')
    assert dialog.get_message() == 'Pick one'

    dialog.set_message('Pick two')

    assert dialog.get_message() == 'Pick two'


def test_set_icon_sets_the_dialogs_icon():
    dialog = SelectDialog()
    icon = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 16, 16)

    dialog.set_icon(icon)

    assert dialog.dialog.get_icon() is icon


def test_item_signals_from_the_list_are_passed_on():
    dialog = SelectDialog()
    item = {'name': 'Open-Tran', 'enabled': True}
    received = []
    for signal in ('item-enabled', 'item-disabled', 'item-selected'):
        dialog.connect(signal, lambda _dialog, got, signal=signal: received.append((signal, got)))

    for signal in ('item-enabled', 'item-disabled', 'item-selected'):
        dialog.sview.emit(signal, item)

    assert received == [('item-enabled', item), ('item-disabled', item), ('item-selected', item)]


def test_run_reports_every_item_when_done(monkeypatch):
    dialog = SelectDialog()
    _run_without_blocking(monkeypatch, dialog)
    done = []
    dialog.connect('selection-done', lambda _dialog, items: done.append(items))

    response = dialog.run(items=[{'name': 'Open-Tran', 'desc': '', 'enabled': True, 'data': 1}])

    assert response == Gtk.ResponseType.CLOSE
    assert [item['name'] for item in done[0]] == ['Open-Tran']
