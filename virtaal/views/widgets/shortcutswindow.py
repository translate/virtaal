#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

# The one binding this doesn't cover: right-click for external
# look-up, mouse-only so it doesn't fit a keyboard-shortcuts window.
# Only imported lazily (see mainview.py's _on_shortcuts()), so _() is
# already installed by the time this module-level list is built.
SHORTCUT_GROUPS = [
    (_("Global"), [
        ("<Primary>o", _("Open a file")),
        ("<Primary>s", _("Save the current file")),
        ("<Primary>w", _("Close the current file")),
        ("<Primary>q", _("Quit Virtaal")),
        ("<Primary>p", _("Show preferences dialog")),
        ("<Alt>Return", _("Show file properties and statistics")),
        ("F11", _("Toggle fullscreen mode")),
        ("<Primary>question", _("Show this Keyboard Shortcuts window")),
    ]),
    (_("Navigation"), [
        ("Return", _("Move to next translation")),
        ("<Primary>Up", _("Move to previous unit")),
        ("<Primary>Down", _("Move to next unit")),
        ("<Primary>Page_Up", _("Move 10 units up")),
        ("<Primary>Page_Down", _("Move 10 units down")),
        ("<Primary>f F3", _("Search")),
        ("<Primary>g", _("Move to next search match")),
        ("<Primary><Shift>g", _("Move to previous search match")),
    ]),
    (_("Units"), [
        ("<Alt>Left", _("Select previous placeable")),
        ("<Alt>Right", _("Select next placeable")),
        ("<Alt>Down", _("Copy the source or selected placeable to the target")),
        ("<Shift>Return", _("Enter a new line")),
        ("<Primary>Return", _('Mark unit "Needs work" as "Translated" and go to the next unit')),
        ("<Primary><Shift>Return", _('Mark unit as "Needs work" and go to the next unit')),
        ("<Primary>z", _("Undo the last change")),
    ]),
    (_("Plug-ins"), [
        ("<Primary>1", _("Use the first translation suggestion")),
        ("F8", _("Show/Hide checks")),
        ("F9", _("Show/Hide translation suggestions")),
        ("Escape", _("Hide translation suggestions, if shown")),
        ("<Primary>t", _("Add a term to the local terminology file")),
    ]),
    (_("Moving focus"), [
        ("Tab", _("Move to the next target field")),
        ("<Shift>Tab", _("Move to the previous target field")),
        ("<Primary>Tab", _("Jump to the language-pair selector")),
        ("<Primary><Shift>Tab", _('Jump to the "Navigation:" mode selector')),
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
