#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
