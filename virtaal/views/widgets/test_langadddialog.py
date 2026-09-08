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


def test_nplurals_setter_accepts_a_value():
    """_set_nplurals() was missing its value parameter entirely - the
    nplurals property setter raised TypeError on any assignment,
    before ever reaching the spin button."""
    dialog = LanguageAddDialog.__new__(LanguageAddDialog)
    dialog.sbtn_nplurals = Gtk.SpinButton.new_with_range(0, 10, 1)

    dialog.nplurals = 3

    assert dialog.sbtn_nplurals.get_value() == 3
