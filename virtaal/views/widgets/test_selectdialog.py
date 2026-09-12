#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.views.widgets.selectdialog import SelectDialog


def test_scrolled_window_propagates_natural_width():
    # A row's inline "Configure..." button (see lookupview.py) got
    # clipped/hidden - a ScrolledWindow doesn't request its child's
    # actual width by default, it just shrinks it instead.
    dialog = SelectDialog()

    scrolled_window = dialog.sview.get_parent()

    assert scrolled_window.get_property('propagate-natural-width')
