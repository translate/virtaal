#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

__all__ = ['forall_widgets']

from gi.repository import Gtk

from virtaal.support.simplegeneric import generic


@generic
def get_children(widget):
    return []


@get_children.when_type(Gtk.Container)
def get_children_container(widget):
    return widget.get_children()

def forall_widgets(f, widget):
    f(widget)
    for child in get_children(widget):
        forall_widgets(f, child)
