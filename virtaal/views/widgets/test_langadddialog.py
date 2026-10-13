#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gi

gi.require_version('Gtk', '3.0')
import pytest
from gi.repository import Gtk

from virtaal.models.langmodel import LanguageModel
from virtaal.views.widgets.langadddialog import LanguageAddDialog


def test_nplurals_spinner_has_a_real_range():
    # sbtn_nplurals had no adjustment configured in the .ui file, so its
    # range defaulted to [0, 0] - any value set on it clamped straight
    # back to zero.
    dialog = LanguageAddDialog()

    dialog.nplurals = 3

    assert dialog.nplurals == 3



def test_plural_note_does_not_stretch_the_dialog():
    # The note under the plural fields set the dialog's width, so a long
    # translation of it widened the whole dialog.
    dialog = LanguageAddDialog()
    note = dialog.gui.get_object('label8')
    natural_width = dialog.dialog.get_preferred_width().natural_width

    note.set_text(note.get_text() * 6)

    assert dialog.dialog.get_preferred_width().natural_width < natural_width * 1.25

def test_nplurals_setter_accepts_a_value():
    """_set_nplurals() was missing its value parameter entirely - the
    nplurals property setter raised TypeError on any assignment,
    before ever reaching the spin button."""
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.sbtn_nplurals = Gtk.SpinButton.new_with_range(0, 10, 1)

    dialog.nplurals = 3

    assert dialog.sbtn_nplurals.get_value() == 3


def _dialog_with_langcode(code, name='Mmoqish'):
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.ent_langname = Gtk.Entry()
    dialog.ent_langname.set_text(name)
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
    dialog = _dialog_with_langcode('qmm')

    assert dialog.check_input_sanity() == ''


def test_check_input_sanity_requires_a_name():
    dialog = _dialog_with_langcode('qmm', name=' ')

    assert dialog.check_input_sanity() != ''


def test_check_input_sanity_rejects_a_langcode_with_a_space():
    dialog = _dialog_with_langcode('q m')

    assert dialog.check_input_sanity() != ''


@pytest.mark.parametrize('code', ['af', 'AF', 'pt-BR'])
def test_check_input_sanity_rejects_a_langcode_already_used(code):
    LanguageModel('en')  # LanguageModel.languages populates lazily on first real use
    dialog = _dialog_with_langcode(code)

    assert dialog.check_input_sanity() != ''


def test_check_input_sanity_accepts_an_existing_language_being_edited():
    LanguageModel('en')
    dialog = _dialog_with_langcode('af')
    dialog._editing = True

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

    def get_transient_for(self):
        return None


def _dialog_with_ok_button(code=''):
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.ent_langname = Gtk.Entry()
    dialog.ent_langname.set_text('Mmoqish')
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
    dialog.ent_langcode.connect('changed', dialog._on_input_changed)

    dialog.ent_langcode.set_text('qmm')

    assert dialog.btn_add_ok.get_sensitive() is True
    assert dialog.btn_add_ok.get_tooltip_text() is None


def test_insensitive_ok_button_says_why():
    dialog = _dialog_with_ok_button('e')

    assert dialog.btn_add_ok.get_tooltip_text() == dialog.check_input_sanity()


def test_run_shows_before_presenting():
    # run() called dialog.run() with no show()/present() beforehand -
    # same #3515/#3525 pattern, show() has to come first since
    # present() only raises an already-realized window.
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.dialog = _FakeDialog()
    dialog.clear = lambda: None
    dialog.btn_add_ok = Gtk.Button()
    dialog.ent_langname = Gtk.Entry()
    dialog.ent_langcode = Gtk.Entry()

    dialog.run()

    assert dialog.dialog.calls == ['show', 'present']


def test_run_edit_prefills_the_language_and_fixes_its_name_and_code():
    dialog = LanguageAddDialog()
    seen = []

    def run(clear=True):
        seen.append((clear, dialog.dialog.get_title(), dialog.ent_langname.get_sensitive(),
                     dialog.ent_langcode.get_sensitive(), dialog.langname, dialog.langcode,
                     dialog.nplurals, dialog.plural))
        return True
    dialog.run = run

    assert dialog.run_edit('Ukrainian', 'uk', 3, 'n%10==1 ? 0 : 1')

    assert seen == [(False, 'Edit Language', False, False, 'Ukrainian', 'uk', 3, 'n%10==1 ? 0 : 1')]
    # Adding a language afterwards gets the add dialog back.
    assert dialog.dialog.get_title() == 'Add Missing Language'
    assert dialog.ent_langname.get_sensitive() and dialog.ent_langcode.get_sensitive()


def test_ok_is_the_default_button():
    dialog = LanguageAddDialog()

    assert dialog.dialog.get_default_widget() is dialog.btn_add_ok


def test_enter_in_any_field_activates_ok():
    # OK stays insensitive until the code is valid, so Enter can't add a bad one.
    dialog = LanguageAddDialog()

    for entry in (dialog.ent_langname, dialog.ent_langcode, dialog.ent_plural, dialog.sbtn_nplurals):
        assert entry.get_activates_default()


def test_run_focuses_the_language_name(monkeypatch):
    dialog = LanguageAddDialog()
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CANCEL)
    dialog.ent_plural.grab_focus()

    dialog.run()

    assert dialog.dialog.get_focus() is dialog.ent_langname


def test_run_edit_focuses_the_first_plural_field(monkeypatch):
    # The name and code can't be edited there.
    dialog = LanguageAddDialog()
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CANCEL)

    dialog.run_edit('Afrikaans', 'af', 2, '(n != 1)')

    assert dialog.dialog.get_focus() is dialog.sbtn_nplurals
