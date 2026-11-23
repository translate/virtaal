#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Menu labels for the macOS menu bar, which has no access keys (#4823).

gtk-mac-integration titles each native item with gtk_label_get_text(),
which drops only the underscore, so a bracketed access key such as
"파일(_F)" shows as "파일(F)"."""

import re

from gi.repository import Gtk

# "(_F)" or "（_F）", with an optional space before it, at the end of
# the label or before a trailing ellipsis or colon. "(__F)" is a
# literal underscore, not an access key.
_BRACKET_MNEMONIC = re.compile(r"\s?[(（]_[^\s_)）][)）](?=(?:…|\.\.\.|:|：)?$)")


def menu_title(label):
    """C{label} without a bracketed access key, as macOS menus show it."""
    return _BRACKET_MNEMONIC.sub("", label, count=1)


def strip_bracket_mnemonics(menu_shell):
    """Removes bracketed access keys from every item of C{menu_shell} and
        its submenus, now and whenever a label or an item changes."""
    if not isinstance(menu_shell, Gtk.MenuShell) or getattr(menu_shell, "_virtaal_mac_titles", False):
        return
    menu_shell._virtaal_mac_titles = True
    menu_shell.connect("insert", lambda shell, item, position: _strip_item(item))
    for item in menu_shell.get_children():
        _strip_item(item)


def _strip_item(item):
    if not isinstance(item, Gtk.MenuItem) or getattr(item, "_virtaal_mac_titles", False):
        return
    item._virtaal_mac_titles = True
    _watch_label(item)
    # set_label() on an item without a label child creates one.
    item.connect("notify::label", lambda item, pspec: _watch_label(item))
    strip_bracket_mnemonics(item.get_submenu())
    item.connect("notify::submenu", lambda item, pspec: strip_bracket_mnemonics(item.get_submenu()))


def _watch_label(item):
    label = item.get_child()
    if not isinstance(label, Gtk.Label):
        return
    _strip_label(label)
    if not getattr(label, "_virtaal_mac_titles", False):
        label._virtaal_mac_titles = True
        label.connect("notify::label", lambda label, pspec: _strip_label(label))


def _strip_label(label):
    if not label.get_use_underline():
        return
    text = label.get_label()
    title = menu_title(text)
    if title != text:
        label.set_label(title)
