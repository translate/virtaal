#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.modeview import ModeView


def test_select_mode_unknown_name_raises_value_error():
    """select_mode()'s ValueError message referenced an undefined
    mode_name (should be displayname) - raised NameError instead of
    the intended ValueError for any unknown mode name."""
    view = ModeView.__new__(ModeView)
    view.displayname_index = {}

    with pytest.raises(ValueError, match='qwerty'):
        view.select_mode('qwerty')


def _view_with_modes(*names):
    view = ModeView.__new__(ModeView)
    view._unavailable = set()
    view.cmb_modes = Gtk.ComboBoxText()
    for name in names:
        view.cmb_modes.append_text(name)
    return view


def _sensitivity(view):
    cell = Gtk.CellRendererText()
    result = {}
    for row in view.cmb_modes.get_model():
        view._set_cell_sensitive(view.cmb_modes, cell, row.model, row.iter)
        result[row[0]] = cell.get_property('sensitive')
    return result


def test_set_unavailable_modes_greys_out_only_those_modes():
    view = _view_with_modes('All', 'Incomplete', 'Search')
    changed = []
    view.cmb_modes.get_model().connect('row-changed', lambda model, path, it: changed.append(str(path)))

    view.set_unavailable_modes(['Incomplete'])

    assert _sensitivity(view) == {'All': True, 'Incomplete': False, 'Search': True}
    assert changed == ['0', '1', '2']


def test_set_unavailable_modes_with_nothing_makes_every_mode_available_again():
    view = _view_with_modes('All', 'Incomplete')
    view.set_unavailable_modes(['Incomplete'])

    view.set_unavailable_modes([])

    assert _sensitivity(view) == {'All': True, 'Incomplete': True}


# Context selector #

def _context_view():
    view = ModeView.__new__(ModeView)
    from virtaal.common import GObjectWrapper
    GObjectWrapper.__init__(view)
    # Kept referenced: a collected top bar destroys the selector with it.
    view.top_bar = Gtk.Box()
    view._build_context_gui(view.top_bar)
    selected = []
    view.connect('context-selected', lambda v, context: selected.append(context))
    return view, selected


def test_context_selector_offers_none_to_all(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'en')
    view, _selected = _context_view()

    assert [row[0] for row in view.cmb_context.get_model()] == ['None', '1', '2', '3', 'All']


def test_context_selector_counts_use_the_ui_languages_digits(monkeypatch):
    import builtins
    real = builtins._
    arabic_indic = '٠١٢٣٤٥٦٧٨٩'
    monkeypatch.setattr(builtins, '_', lambda s: arabic_indic if s == '0123456789' else real(s))

    view, _selected = _context_view()

    assert [row[0] for row in view.cmb_context.get_model()][1:4] == ['١', '٢', '٣']
    view.cmb_context.set_active_id('2')
    assert view.cmb_context.get_active_id() == '2'


def test_choosing_a_context_emits_it():
    view, selected = _context_view()

    view.cmb_context.set_active_id('2')
    view.cmb_context.set_active_id('0')
    view.cmb_context.set_active_id('all')

    assert selected == [2, 0, None]


def test_select_context_shows_it_without_emitting():
    view, selected = _context_view()

    view.select_context(3)
    view.select_context(None)

    assert view.cmb_context.get_active_id() == 'all'
    assert selected == []



def test_the_navigation_mnemonic_opens_the_mode_list():
    view = _view_with_modes('All', 'Incomplete')
    calls = []
    view.cmb_modes.grab_focus = lambda: calls.append('focus')
    view.cmb_modes.popup = lambda: calls.append('popup')

    assert view._on_cmbmode_mnemonic(view.cmb_modes, False) is True
    assert calls == ['focus', 'popup']


def test_focus_opens_the_mode_list():
    # Ctrl+Shift+Tab from the translation.
    view = _view_with_modes('All', 'Incomplete')
    calls = []
    view.cmb_modes.grab_focus = lambda: calls.append('focus')
    view.cmb_modes.popup = lambda: calls.append('popup')

    view.focus()

    assert calls == ['focus', 'popup']
