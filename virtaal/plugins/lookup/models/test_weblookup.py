#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.plugins.lookup.models.weblookup import WebLookupConfigDialog


def test_treeview_scrolled_window_is_not_focusable():
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the treeview inside it (confirmed live: Right-arrow/Down got
    # stuck, same issue as prefsview.py's plugin/placeables lists).
    dialog = WebLookupConfigDialog(parent=None)

    assert not dialog.tvw_urls.get_parent().get_can_focus()
