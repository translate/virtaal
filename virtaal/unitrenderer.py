#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright (C) 2005-2007 Osmo Salomaa
# Copyright (C) 2007 Zuza Software Foundation
#
# This file was part of Gaupol.
# This file is part of virtaal.
#
# virtaal is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Translate is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Translate.  If not, see <http://www.gnu.org/licenses/>.

"""Cell renderer for multiline text data."""

import gobject
import gtk
import pango

import markup
import undo_buffer
from unit_editor import UnitEditor
import unit_layout


def undo(tree_view):
    undo_buffer.undo(tree_view.get_buffer().undo_list)

class UnitRenderer(gtk.GenericCellRenderer):
    """Cell renderer for multiline text data."""

    __gtype_name__ = "UnitRenderer"
    
    __gproperties__ = {
        "unit":     (gobject.TYPE_PYOBJECT, 
                    "The unit",
                    "The unit that this renderer is currently handling",
                    gobject.PARAM_READWRITE),
        "editable": (gobject.TYPE_BOOLEAN,
                    "editable", 
                    "A boolean indicating whether this unit is currently editable",
                    False,
                    gobject.PARAM_READWRITE),
    }
 
    __gsignals__ = {
        "unit-edited":  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                        (gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN)),
        "modified":     (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    def __init__(self, nplurals=None):
        gtk.GenericCellRenderer.__init__(self)
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)

        self.__unit = None
        self.editable = False
        self._editor = None
        self._nplurals = nplurals
        self._modified_widget = None
        self.source_layout = None
        self.target_layout = None

    def get_unit(self):
        return self.__unit

    def set_unit(self, value):        
        if value.isfuzzy():
            self.props.cell_background = "gray"
            self.props.cell_background_set = True

        else:
            self.props.cell_background_set = False
        
        self.__unit = value

    unit = property(get_unit, set_unit, None, None)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_render(self, window, widget, _background_area, cell_area, _expose_area, _flags):
        if self.editable:
            return True
        x_offset, y_offset, width, _height = self.do_get_size(widget, cell_area)
        x = cell_area.x + x_offset
        y = cell_area.y + y_offset
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
                cell_area, widget, '', x, y, self.source_layout)
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
                cell_area, widget, '', x + width/2, y, self.target_layout)

    def get_pango_layout(self, widget, text, width):
        '''Gets the Pango layout used in the cell in a TreeView widget.'''
        layout = pango.Layout(widget.get_pango_context())
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_width(width * pango.SCALE)

        #XXX - plurals?
        text = text or ""
#        layout.set_text(text)
        layout.set_markup(markup.markuptext(text))
        return layout
    
    def compute_cell_height(self, widget, width):
        self.source_layout = self.get_pango_layout(widget, self.unit.source, width / 2)
        self.target_layout = self.get_pango_layout(widget, self.unit.target, width / 2)
        _layout_width, source_height = self.source_layout.get_pixel_size()
        _layout_width, target_height = self.target_layout.get_pixel_size()
        return max(source_height, target_height)

    def do_get_size(self, widget, _cell_area):
        xpad = 2
        ypad = 2

        #TODO: store last unitid and computed dimensions
        width = widget.get_toplevel().get_allocation().width - 32

        if self.editable:
            height = unit_layout.get_blueprints(self.unit, widget).height(width)
        else:
            height = self.compute_cell_height(widget, width)

        # XXX - comments
        width  = width  + (xpad * 2)
        height = height + (ypad * 2)

        height = min(height, 600)
        return xpad, ypad, width, height

    def _on_editor_done(self, editor):
        self.emit("unit-edited", editor.get_data("path"), editor.get_text(), editor.must_advance, editor.get_modified())
        return True

    def _on_modified(self, editor):
        self._modified_widget = editor
        self.emit("modified")
        return True

    def update_for_save(self, _away=False):
        """Prepare all data structures for saving.

        away indicates that this is because we want to move to another cell."""
        if self._modified_widget:
            self._modified_widget.update_for_save()
#            if away:
#                self._modified_widget.editing_done()

    def do_start_editing(self, _event, widget, path, _bg_area, cell_area, _flags):
        """Initialize and return the editor widget."""
        editor = UnitEditor(widget, self.unit)
        editor.set_size_request(cell_area.width, cell_area.height-2)
        editor.set_border_width(min(self.props.xpad, self.props.ypad))
        editor.set_data("path", path)
        editor.connect("editing-done", self._on_editor_done)
        editor.connect("modified", self._on_modified)
        editor.show_all()
        widget.editor = editor
        self._editor = editor
        return editor
