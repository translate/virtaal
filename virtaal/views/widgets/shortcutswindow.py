#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.common.platform import platform
from virtaal.support.libi18n.numbers import localise_digits

# The one binding this doesn't cover: right-click for external
# look-up, mouse-only so it doesn't fit a keyboard-shortcuts window.
# Only imported lazily (see mainview.py's _on_shortcuts()), so _() is
# already installed by the time this module-level list is built.
SHORTCUT_GROUPS = [
    (_("Global"), [
        ("<Primary>o", _("Open a file")),
        ("<Primary>s", _("Save the current file")),
        ("<Primary><Shift>s", _("Save the current file under a new name")),
        ("<Primary>w", _("Close the current file")),
        ("<Primary>q", _("Quit Virtaal")),
        ("<Primary>p", _("Show preferences dialog")),
        ("<Primary>i" if platform.is_mac else "<Alt>Return", _("Show file properties and statistics")),
        ("F11", _("Toggle fullscreen mode")),
        ("<Primary>slash" if platform.is_mac else "<Primary>question", _("Show this Keyboard Shortcuts window")),
    ]),
    (_("Navigation"), [
        ("Return", _("Move to next translation")),
        ("<Primary>Up", _("Move to previous unit")),
        ("<Primary>Down", _("Move to next unit")),
        ("<Primary>Page_Up", _("Move 10 units up")),
        ("<Primary>Page_Down", _("Move 10 units down")),
        ("<Primary>Home", _("Move to first unit")),
        ("<Primary>End", _("Move to last unit")),
        ("<Primary>f F3", _("Search")),
        ("<Primary>g", _("Move to next search match")),
        ("<Primary><Shift>g", _("Move to previous search match")),
    ]),
    (_("Units"), [
        ("<Alt>Left", _("Select previous placeable")),
        ("<Alt>Right", _("Select next placeable")),
        ("<Alt>Down", _("Insert the selected placeable")),
        ("<Primary><Shift>v", _("Replace the translation with the source")),
        ("<Primary>c", _("Copy the source, if nothing is selected")),
        ("<Shift>Return", _("Enter a new line")),
        ("<Control>Return", _("Next Unit and Advance State")),
        ("<Control><Shift>Return", _("Next Unit and Reverse State")),
        ("<Primary>z", _("Undo the last change")),
        ("<Primary><Shift>z", _("Redo the last undone change")),
    ]),
    (_("Plug-ins"), [
        ("<Primary>1", _("Use the first translation suggestion")),
        ("F8", _("Show/Hide checks")),
        ("F9", _("Show translation suggestions for this unit")),
        ("<Primary>F9", _("Turn translation suggestions on or off")),
        ("Escape", _("Hide translation suggestions, if shown")),
        ("<Primary>t", _("Add a term to the local terminology file")),
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
        self._localise_page_numbers(section)
        self.add(section)
        self.show()

    def _localise_page_numbers(self, section):
        # GTK titles a long section's pages "_1", "_2", ... itself, in an
        # internal stack it rebuilds on every reflow, untranslated.
        children = []
        section.forall(children.append)
        for stack in children:
            if isinstance(stack, Gtk.Stack):
                stack.connect('add', self._on_page_added)

    def _on_page_added(self, stack, page):
        page.connect('child-notify::title', self._on_page_title_changed, stack)

    @staticmethod
    def _on_page_title_changed(page, pspec, stack):
        title = stack.child_get_property(page, 'title')
        if title and localise_digits(title) != title:
            stack.child_set_property(page, 'title', localise_digits(title))
