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

import pytest

from virtaal.views.modeview import ModeView


def test_select_mode_unknown_name_raises_value_error():
    """select_mode()'s ValueError message referenced an undefined
    mode_name (should be displayname) - raised NameError instead of
    the intended ValueError for any unknown mode name."""
    view = ModeView.__new__(ModeView)
    view.displayname_index = {}

    with pytest.raises(ValueError, match='qwerty'):
        view.select_mode('qwerty')
