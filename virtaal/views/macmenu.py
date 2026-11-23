#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Labels without bracketed access keys, for macOS (#4823).

macOS has no access keys: gtk-mac-integration titles each native menu
item with gtk_label_get_text(), which drops only the underscore, and
GTK shows no underline in windows, so "파일(_F)" showed as "파일(F)"."""

import re

from gi.repository import GObject, Gtk

# "(_F)" or "（_F）", with an optional space before it or inside the
# brackets. "(__F)" is a literal underscore, not an access key.
_BRACKET_MNEMONIC = re.compile(r"\s?[(（]\s*_[^\s_)）]\s*[)）]")


def menu_title(label):
    """C{label} without bracketed access keys, as macOS shows it."""
    return _BRACKET_MNEMONIC.sub("", label)


def strip_window_access_keys():
    """Removes bracketed access keys from every label with an access key,
        in the windows already open and in every label realized later.
        Returns the emission hook's id."""
    hook_id = GObject.add_emission_hook(Gtk.Widget, "realize", _on_realize)
    for window in Gtk.Window.list_toplevels():
        _watch_tree(window)
    return hook_id


def _on_realize(widget, *args):
    if isinstance(widget, Gtk.Label):
        _watch(widget)
    return True


def _watch_tree(widget):
    if isinstance(widget, Gtk.Label):
        _watch(widget)
    elif isinstance(widget, Gtk.Container):
        widget.forall(_watch_tree)


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


def _find_label(widget):
    if isinstance(widget, Gtk.Label):
        return widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            label = _find_label(child)
            if label is not None:
                return label
    return None


def _watch_label(item):
    # gtk-mac-integration also takes the first label below the item.
    label = _find_label(item.get_child())
    if label is None:
        return
    _watch(label)


def _watch(label):
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
