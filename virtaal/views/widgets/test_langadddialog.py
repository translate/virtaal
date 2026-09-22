#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from virtaal.views.widgets.langadddialog import LanguageAddDialog


def test_nplurals_spinner_has_a_real_range():
    # sbtn_nplurals had no adjustment configured in the .ui file, so its
    # range defaulted to [0, 0] - any value set on it clamped straight
    # back to zero.
    dialog = LanguageAddDialog()

    dialog.nplurals = 3

    assert dialog.nplurals == 3


def test_nplurals_setter_accepts_a_value():
    """_set_nplurals() was missing its value parameter entirely - the
    nplurals property setter raised TypeError on any assignment,
    before ever reaching the spin button."""
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.sbtn_nplurals = Gtk.SpinButton.new_with_range(0, 10, 1)

    dialog.nplurals = 3

    assert dialog.sbtn_nplurals.get_value() == 3


def _dialog_with_langcode(code):
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.ent_langcode = Gtk.Entry()
    dialog.ent_langcode.set_text(code)
    return dialog


def test_check_input_sanity_rejects_a_non_ascii_langcode():
    """check_input_sanity() used str(code, 'ascii') to validate the code
    - a Python 2 idiom for decoding bytes that raises TypeError on a
    str in Python 3, rather than reporting the code as invalid (#3532)."""
    dialog = _dialog_with_langcode('ém')

    assert dialog.check_input_sanity() != ''


def test_check_input_sanity_accepts_an_ascii_langcode():
    dialog = _dialog_with_langcode('en')

    assert dialog.check_input_sanity() == ''


class _FakeDialog:
    def __init__(self):
        self.calls = []

    def show(self):
        self.calls.append('show')

    def present(self):
        self.calls.append('present')

    def run(self):
        return Gtk.ResponseType.CANCEL

    def hide(self):
        pass


def _dialog_with_ok_button(code=''):
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.ent_langcode = Gtk.Entry()
    dialog.ent_langcode.set_text(code)
    dialog.btn_add_ok = Gtk.Button()
    dialog._update_ok_sensitivity()
    return dialog


def test_ok_button_is_insensitive_for_a_too_short_langcode():
    dialog = _dialog_with_ok_button('e')

    assert dialog.btn_add_ok.get_sensitive() is False


def test_ok_button_becomes_sensitive_once_the_langcode_is_valid():
    dialog = _dialog_with_ok_button()
    dialog.ent_langcode.connect('changed', dialog._on_langcode_changed)

    dialog.ent_langcode.set_text('en')

    assert dialog.btn_add_ok.get_sensitive() is True


def test_run_shows_before_presenting():
    # run() called dialog.run() with no show()/present() beforehand -
    # same #3515/#3525 pattern, show() has to come first since
    # present() only raises an already-realized window.
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.dialog = _FakeDialog()
    dialog.clear = lambda: None
    dialog.btn_add_ok = Gtk.Button()
    dialog.ent_langcode = Gtk.Entry()

    dialog.run()

    assert dialog.dialog.calls == ['show', 'present']
