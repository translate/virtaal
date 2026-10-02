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
