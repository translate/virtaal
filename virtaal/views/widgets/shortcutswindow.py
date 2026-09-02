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

from gi.repository import Gtk

# The one binding this doesn't cover: right-click for external
# look-up, mouse-only so it doesn't fit a keyboard-shortcuts window.
# Only imported lazily (see mainview.py's _on_shortcuts()), so _() is
# already installed by the time this module-level list is built.
SHORTCUT_GROUPS = [
    (_("Global"), [
        ("<Control>o", _("Open a file")),
        ("<Control>s", _("Save the current file")),
        ("<Control>w", _("Close the current file")),
        ("<Control>q", _("Quit Virtaal")),
        ("<Control>p", _("Show preferences dialog")),
        ("<Alt>Return", _("Show file properties and statistics")),
        ("F11", _("Toggle fullscreen mode")),
        ("<Control>question", _("Show this Keyboard Shortcuts window")),
    ]),
    (_("Navigation"), [
        ("Return", _("Move to next translation")),
        ("<Control>Up", _("Move to previous unit")),
        ("<Control>Down", _("Move to next unit")),
        ("<Control>Page_Up", _("Move 10 units up")),
        ("<Control>Page_Down", _("Move 10 units down")),
        ("<Control>f F3", _("Search")),
        ("<Control>g", _("Move to next search match")),
        ("<Control><Shift>g", _("Move to previous search match")),
    ]),
    (_("Units"), [
        ("<Alt>Left", _("Select previous placeable")),
        ("<Alt>Right", _("Select next placeable")),
        ("<Alt>Down", _("Copy the source or selected placeable to the target")),
        ("<Shift>Return", _("Enter a new line")),
        ("<Control>Return", _('Mark unit "Needs work" as "Translated" and go to the next unit')),
        ("<Control><Shift>Return", _('Mark unit as "Needs work" and go to the next unit')),
        ("<Control>z", _("Undo the last change")),
    ]),
    (_("Plug-ins"), [
        ("<Control>1", _("Use the first translation suggestion")),
        ("F8", _("Show/Hide checks")),
        ("F9", _("Show/Hide translation suggestions")),
        ("Escape", _("Hide translation suggestions, if shown")),
        ("<Control>t", _("Add a term to the local terminology file")),
    ]),
    (_("Moving focus"), [
        ("Tab", _("Move to the next target field")),
        ("<Shift>Tab", _("Move to the previous target field")),
        ("<Control>Tab", _("Jump to the language-pair selector")),
        ("<Control><Shift>Tab", _('Jump to the "Navigation:" mode selector')),
        ("Escape", _("Close the search bar and return to normal editing")),
    ]),
]


class ShortcutsWindow(Gtk.ShortcutsWindow):
    """A native GTK shortcuts-overview window, built from SHORTCUT_GROUPS,
        reachable from Help > Keyboard Shortcuts."""

    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=False)
        section = Gtk.ShortcutsSection(visible=True, section_name="virtaal")
        for title, shortcuts in SHORTCUT_GROUPS:
            group = Gtk.ShortcutsGroup(visible=True, title=title)
            for accelerator, desc in shortcuts:
                group.add(Gtk.ShortcutsShortcut(
                    visible=True, accelerator=accelerator, title=desc))
            section.add(group)
        self.add(section)
        self.show()
