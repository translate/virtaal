#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.widgets.shortcutswindow import SHORTCUT_GROUPS, ShortcutsWindow


def test_every_group_has_a_title_and_at_least_one_shortcut():
    for title, shortcuts in SHORTCUT_GROUPS:
        assert title
        assert len(shortcuts) > 0
        for accelerator, description in shortcuts:
            assert accelerator
            assert description


def test_construction_builds_a_window_from_every_group():
    parent = Gtk.Window()

    window = ShortcutsWindow(parent)

    assert window.get_transient_for() is parent
    window.destroy()
    parent.destroy()
