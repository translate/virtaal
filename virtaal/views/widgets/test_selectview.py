#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.views.widgets.selectview import SelectView


def test_select_item_finds_a_row_that_is_not_the_first():
    # The search loop never advanced its iterator past the first row -
    # selecting anything else spun forever at 100% CPU.
    sview = SelectView(items=[
        {'name': 'A', 'desc': '', 'enabled': False, 'data': 'a'},
        {'name': 'B', 'desc': '', 'enabled': False, 'data': 'b'},
    ])
    target = sview.get_all_items()[1]

    sview.select_item(target)

    assert sview.get_selected_item() == target
