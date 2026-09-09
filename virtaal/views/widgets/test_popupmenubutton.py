#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regression tests for Release Blocker #8 (a native segfault from popup-menu
teardown racing Python's GC - see WorkflowMode/QualityCheckMode's own
_add_widgets() comment for the full mechanism). The crash itself was only
~30% reproducible and kills the whole test process on a hit, so it can't be
tested directly - these instead assert the fix's actual invariant: a
replaced menu is destroy()ed deterministically, not just dropped for GC to
collect whenever and however it likes."""

from unittest.mock import MagicMock

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from virtaal.views.widgets.popupmenubutton import PopupMenuButton


def test_set_menu_destroys_previous_menu():
    button = PopupMenuButton()
    old_menu = button.menu
    old_menu.destroy = MagicMock()

    button.set_menu(Gtk.Menu())

    assert old_menu.destroy.called


def test_set_menu_first_call_does_not_destroy_anything():
    # __init__ itself calls set_menu() before self.menu exists yet -
    # this must not error trying to destroy a non-existent old menu.
    PopupMenuButton()
