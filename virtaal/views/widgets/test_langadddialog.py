#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

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
