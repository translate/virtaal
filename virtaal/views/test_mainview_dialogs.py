#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""MainView's own dialogs, built for real. Only Gtk.Dialog.run(), which
blocks until a button is pressed, is replaced."""

import gi
import pytest

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

from virtaal.views.mainview import EntryDialog, MainView


@pytest.fixture
def view(monkeypatch):
    view = MainView.__new__(MainView)
    view.main_window = Gtk.Window()
    view._top_window = view.main_window
    # show_*_dialog() hands focus back to the main window from an idle.
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: None)
    yield view
    for name in ('input_dialog', 'error_dialog', 'prompt_dialog', 'info_dialog', 'confirm_dialog'):
        if name in view.__dict__:
            view.__dict__[name].destroy()
    view.main_window.destroy()


def _button_labels(widget):
    # A set: Windows lays the buttons out in the alternative order.
    if isinstance(widget, Gtk.Button):
        return {widget.get_label()}
    if isinstance(widget, Gtk.Container):
        return {label for child in widget.get_children() for label in _button_labels(child)}
    return set()


def _press(monkeypatch, response, typed=None):
    """Make Gtk.Dialog.run() return C{response}, after typing C{typed}
        into an EntryDialog."""
    def run(dialog):
        if typed is not None:
            dialog.ent_input.set_text(typed)
        return response
    monkeypatch.setattr(Gtk.Dialog, 'run', run)


@pytest.mark.parametrize('name, message_type', [
    ('error_dialog', Gtk.MessageType.ERROR),
    ('prompt_dialog', Gtk.MessageType.QUESTION),
    ('info_dialog', Gtk.MessageType.INFO),
    ('confirm_dialog', Gtk.MessageType.QUESTION),
])
def test_message_dialogs_are_modal_on_the_main_window(view, name, message_type):
    dialog = getattr(view, name)

    assert dialog.get_transient_for() is view.main_window
    assert dialog.get_modal()
    assert dialog.props.message_type == message_type
    assert getattr(view, name) is dialog


def test_error_dialog_has_an_ok_button_and_a_title(view):
    assert _button_labels(view.error_dialog) == {'_OK'}
    assert view.error_dialog.get_title() == 'Error'


def test_info_dialog_has_an_ok_button(view):
    assert _button_labels(view.info_dialog) == {'_OK'}


def test_prompt_dialog_defaults_to_no(view):
    dialog = view.prompt_dialog

    assert _button_labels(dialog) == {'_No', '_Yes'}
    assert dialog.get_widget_for_response(Gtk.ResponseType.NO).has_default()


def test_confirm_dialog_offers_save_discard_and_cancel_defaulting_to_save(view):
    dialog = view.confirm_dialog
    save = dialog.get_widget_for_response(Gtk.ResponseType.YES)

    assert _button_labels(dialog) == {'_Save', '_Discard', '_Cancel'}
    assert dialog.get_widget_for_response(Gtk.ResponseType.NO).get_label() == '_Discard'
    assert dialog.get_widget_for_response(Gtk.ResponseType.CANCEL).get_label() == '_Cancel'
    assert save.has_default()
    # show_save_confirm_dialog() focuses this button.
    assert dialog._MainView__save_button is save


@pytest.mark.parametrize('response, expected', [
    (Gtk.ResponseType.YES, 'save'),
    (Gtk.ResponseType.NO, 'discard'),
    (Gtk.ResponseType.CANCEL, 'cancel'),
    (Gtk.ResponseType.DELETE_EVENT, 'cancel'),
])
def test_show_save_confirm_dialog_runs_the_real_dialog(view, monkeypatch, response, expected):
    _press(monkeypatch, response)

    assert view.show_save_confirm_dialog() == expected
    assert not view.confirm_dialog.get_visible()
    assert view._top_window is view.main_window


def test_input_dialog_is_an_entry_dialog_on_the_main_window(view):
    dialog = view.input_dialog

    assert isinstance(dialog, EntryDialog)
    assert dialog.get_transient_for() is view.main_window
    assert _button_labels(dialog) == {'_Cancel', '_OK'}
    assert dialog.get_widget_for_response(Gtk.ResponseType.OK).has_default()
    # Enter in the entry presses OK.
    assert dialog.ent_input.get_activates_default()


def test_show_input_dialog_returns_the_text_on_ok(view, monkeypatch):
    _press(monkeypatch, Gtk.ResponseType.OK, typed='Some text')

    assert view.show_input_dialog(title='Rename', message='<b>New name</b>') == 'Some text'
    dialog = view.input_dialog
    assert dialog.get_title() == 'Rename'
    assert dialog.lbl_message.get_text() == 'New name'
    assert not dialog.get_visible()
    assert view._top_window is view.main_window


@pytest.mark.parametrize('response', [Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT])
def test_show_input_dialog_returns_none_unless_ok(view, monkeypatch, response):
    _press(monkeypatch, response, typed='Some text')

    assert view.show_input_dialog(title='Rename', message='New name') is None
    assert view._top_window is view.main_window


def test_entry_dialog_clears_the_last_input_unless_asked_to_keep_it(view, monkeypatch):
    dialog = view.input_dialog
    _press(monkeypatch, Gtk.ResponseType.OK)
    dialog.ent_input.set_text('old')

    assert dialog.run(keepInput=True) == (Gtk.ResponseType.OK, 'old')
    assert dialog.run() == (Gtk.ResponseType.OK, '')


def test_entry_dialog_keeps_its_title_and_message_when_given_none(view, monkeypatch):
    dialog = view.input_dialog
    dialog.set_title('Kept title')
    dialog.set_message('Kept message')
    _press(monkeypatch, Gtk.ResponseType.CANCEL)

    dialog.run()

    assert dialog.get_title() == 'Kept title'
    assert dialog.lbl_message.get_text() == 'Kept message'
