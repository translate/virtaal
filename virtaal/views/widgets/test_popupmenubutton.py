#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
