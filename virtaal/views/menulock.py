#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Greys out a window's menu items while a dialog over it has the focus:
macOS keeps the main window's menu bar live then (#4611)."""

from gi.repository import Gtk


class MenuLock:
    """Greys out every menu item without a submenu, except C{keep}, and puts
        each one back as it was, or as Virtaal set it while greyed."""

    def __init__(self, get_menu_shell, keep=()):
        self._get_menu_shell = get_menu_shell
        self._keep = list(keep)
        # Each greyed item's own sensitivity.
        self._saved = {}

    @property
    def locked(self):
        return bool(self._saved)

    def lock(self):
        if self.locked:
            return
        for item in self._items(self._get_menu_shell()):
            if any(item is kept for kept in self._keep):
                continue
            self._saved[item] = item.get_sensitive()
            Gtk.Widget.set_sensitive(item, False)
            # Keep what Virtaal sets while greyed, to put it back on unlock.
            item.set_sensitive = lambda sensitive, item=item: self._saved.__setitem__(item, bool(sensitive))

    def unlock(self):
        saved, self._saved = self._saved, {}
        for item, sensitive in saved.items():
            del item.set_sensitive
            item.set_sensitive(sensitive)

    def _items(self, shell):
        """Menu items without a submenu: a top-level menu stays openable."""
        for item in shell.get_children():
            if not isinstance(item, Gtk.MenuItem) or isinstance(item, Gtk.SeparatorMenuItem):
                continue
            submenu = item.get_submenu()
            if submenu is None:
                yield item
            else:
                yield from self._items(submenu)
