#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest

from virtaal.modes.basemode import BaseMode


def test_init_is_not_implemented():
    with pytest.raises(NotImplementedError):
        BaseMode(None)


def test_selected_is_not_implemented():
    mode = BaseMode.__new__(BaseMode)
    with pytest.raises(NotImplementedError):
        mode.selected()


def test_unselected_is_not_implemented():
    mode = BaseMode.__new__(BaseMode)
    with pytest.raises(NotImplementedError):
        mode.unselected()
