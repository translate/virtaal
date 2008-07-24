#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import gobject
import pango
import gtk

from translate.misc.multistring import multistring

import markup
import unit_layout
import widgets.label_expander as label_expander
from support.simplegeneric import generic

@generic
def compute_optimal_height(widget, width):
    raise NotImplementedError()

@compute_optimal_height.when_type(gtk.Widget)
def gtk_widget_compute_optimal_height(widget, width):
    pass

@compute_optimal_height.when_type(gtk.Container)
def gtk_container_compute_optimal_height(widget, width):
    for child in widget.get_children():
        compute_optimal_height(child, width)

@compute_optimal_height.when_type(gtk.Table)
def gtk_table_compute_optimal_height(widget, width):
    for child in widget.get_children():
        compute_optimal_height(child, width / 2)

def make_pango_layout(layout, text, widget, width):
    pango_layout = pango.Layout(widget.get_pango_context())
    pango_layout.set_width(width * pango.SCALE)
    pango_layout.set_wrap(pango.WRAP_WORD)
    pango_layout.set_text(text or "")
    return pango_layout

@compute_optimal_height.when_type(gtk.TextView)
def gtk_textview_compute_optimal_height(widget, width):
    l = gtk.Layout()
    buf = widget.get_buffer()
    # For border calculations, see gtktextview.c:gtk_text_view_size_request in the GTK source 
    border = 2 * widget.border_width - 2 * widget.parent.border_width
    if widget.style_get_property("interior-focus"):
        border += 2 * widget.style_get_property("focus-line-width")
    _w, h = make_pango_layout(widget, buf.get_text(buf.get_start_iter(), buf.get_end_iter()), l, width - border).get_pixel_size()
    widget.parent.set_size_request(-1, h + border)

@compute_optimal_height.when_type(label_expander.LabelExpander)
def gtk_labelexpander_compute_optimal_height(widget, width):
    if widget.label.child.get_text().strip() == "":
        widget.set_size_request(-1, 0)
    else:
        l = gtk.Layout()
        _w, h = make_pango_layout(widget, widget.label.child.get_label()[0], l, width).get_pixel_size()
        widget.set_size_request(-1, h + 4)

class UnitEditor(gtk.EventBox, gtk.CellEditable):
    """Text view suitable for cell renderer use."""

    __gtype_name__ = "UnitEditor"

    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    def __init__(self, parent, unit):
        gtk.EventBox.__init__(self)
        self.layout = unit_layout.build_layout(unit, parent.document.nplurals)
        self.add(self.layout)
        for target in unit_layout.get_targets(self.layout):
            target.get_buffer().connect("changed", self._on_modify)
        self.must_advance = False
        self._modified = False
        self._unit = unit
        self.connect('key-press-event', self._on_key_press_event)

    def _on_modify(self, _buf):
        self.emit('modified')

    def _on_key_press_event(self, _widget, event, *_args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            self.must_advance = True
            self.editing_done()

    def do_start_editing(self, *_args):
        """Start editing."""
        unit_layout.focus_text_view(unit_layout.get_targets(self)[0])

    def _on_focus(self, widget, _direction):
        # TODO: Check whether we do need to refocus the last edited text_view when
        #       our program gets focus after having lost it.
        self.recent_textview = widget
        return False

    def _on_modified(self, widget):
        if widget in self.buffers:
            self.fuzzy_checkbox.set_active(False)
        elif self.recent_textview:
            self.recent_textview.grab_focus()
        self.emit("modified")
        self._modified = True
        return False

    def get_modified(self):
        return self._modified

    def get_text(self):
        targets = [b.props.text for b in self.buffers]
        if len(targets) == 1:
            return targets[0]
        else:
            return multistring(targets)

    def _on_copy_original(self, _widget):
        for buf in self.buffers:
            buf.set_text(markup.escape(self._unit.source))
            self.do_start_editing()
        return True
