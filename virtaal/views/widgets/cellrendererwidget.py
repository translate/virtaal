#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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
from gi.repository import GLib
from gi.repository import Pango
from gi.repository import GObject


def flagstr(flags):
    """Create a string-representation for the given flags structure."""
    return "FIXME"
    # FIXME - this doesn't work but is only used in debugging code
    fset = []
    for f in dir(Gtk):
        if not f.startswith('CellRenderer'):
            continue
        print flags
        print getattr(Gtk, f)
        if flags & getattr(Gtk, f):
            fset.append(f)
    return '|'.join(fset)


class CellRendererWidget(Gtk.CellRenderer):
    __gtype_name__ = 'CellRendererWidget'
    __gproperties__ = {
        'widget': (GObject.TYPE_PYOBJECT, 'Widget', 'The column containing the widget to render', GObject.PARAM_READWRITE),
    }

    XPAD = 2
    YPAD = 2


    # INITIALIZERS #
    def __init__(self, strfunc, default_width=-1):
        GObject.GObject.__init__(self)
        #super(CellRendererWidget, self).__init__()

        self.default_width = default_width
        self._editing = False
        self.strfunc = strfunc
        self.widget = None


    # INTERFACE METHODS #
    # FIXME these don't seem to be in the Gtk C implementation
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_size(self, widget, cell_area=None):
        print '%s>> get_size()' % (self.strfunc(self.widget))
        # FIXME: This method works fine for unselected cells (rows) and gives the same (wrong) results for selected cells.
        height = width = 0

        if cell_area is not None:
            return self.XPAD, self.YPAD, cell_area.width - 2*self.XPAD, cell_area.height - 2*self.YPAD

        width = widget.get_allocation().width
        if width <= 1:
            width = self.default_width
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, width)
        width, height = layout.get_pixel_size()

        if self.widget:
            requisition = self.widget.size_request()
            width =  max(width,  requisition.width)
            height = max(height, requisition.height)

        #print 'width %d | height %d | lw %d | lh %d' % (width, height, lw, lh)
        height += self.YPAD * 2
        width  += self.XPAD * 2

        return self.XPAD, self.YPAD, width, height

    def do_render(self, window, widget, bg_area, cell_area, flags):
        print '%s>> render(flags=%s)' % (self.strfunc(self.widget), flagstr(flags))
        if flags & Gtk.CellRendererState.SELECTED:
            self.props.mode = Gtk.CellRendererMode.EDITABLE
            self._start_editing(widget) # FIXME: This is obviously a hack, but what more do you want?
            return True
        self.props.mode = Gtk.CellRendererMode.INERT
        xo, yo, w, h = self.get_size(widget, cell_area)
        x = cell_area.x + xo
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, w)
        layout_w, layout_h = layout.get_pixel_size()
        y = cell_area.y + yo + (h-layout_h)/2
        # FIXME widget.get_style().paint_layout(window, Gtk.StateType.NORMAL, True, cell_area, widget, '', x, y, layout)

    def do_start_editing(self, event, tree_view, path, bg_area, cell_area, flags):
        print '%s>> start_editing(flags=%s, event=%s)' % (self.strfunc(self.widget), flagstr(flags), event)
        editable = self.widget
        if not isinstance(editable, Gtk.CellEditable):
            editable = CellWidget(editable)
        editable.show_all()
        editable.grab_focus()
        return editable

    # METHODS #
    def create_pango_layout(self, string, widget, width):
        font = widget.get_pango_context().get_font_description()
        layout = Pango.Layout(widget.get_pango_context())
        layout.set_font_description(font)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_width(width * Pango.SCALE)
        layout.set_markup(string, len(string))
        # This makes no sense, but mostly has the desired effect to align things correctly for
        # RTL languages which is otherwise incorrect. Untranslated entries is still wrong.
        if widget.get_direction() == Gtk.TextDirection.RTL:
            layout.set_alignment(Pango.Alignment.RIGHT)
            layout.set_auto_dir(False)
        return layout

    def _start_editing(self, treeview):
        """Force the cell to enter editing mode by going through the parent
            Gtk.TextView."""
        if self._editing:
            return
        self._editing = True

        model, iter = treeview.get_selection().get_selected()
        path = model.get_path(iter)
        # FIXME col = [c for c in treeview.get_columns() if self in c.get_cell_renderers()]
        col = [c for c in treeview.get_columns()]
        if len(col) < 1:
            self._editing = False
            return
        treeview.set_cursor_on_cell(path, col[0], self, True)
        # XXX: Hack to make sure that the lock (_start_editing) is not released before the next on_render() is called.
        def update_lock():
            self._editing = False
        GLib.idle_add(update_lock)


class CellWidget(Gtk.HBox, Gtk.CellEditable):
    __gtype_name__ = 'CellWidget'
    __gsignals__ = {
        'modified': (GObject.SignalFlags.RUN_FIRST, None, ())
    }
    __gproperties__ = {
        'editing-canceled': (bool, 'Editing cancelled', 'Editing was cancelled', False, GObject.PARAM_READWRITE),
    }

    # INITIALIZERS #
    def __init__(self, *widgets):
        super(CellWidget, self).__init__()
        for w in widgets:
            if w.get_parent() is not None:
                parent = w.get_parent()
                parent.remove(w)
            self.pack_start(w, True, True, 0)


    # INTERFACE METHODS #
    def editing_done(self, *args):
        pass

    def remove_widget(self, *args):
        pass

    def start_editing(self, *args):
        pass


if __name__ == "__main__":
    class Tree(Gtk.TreeView):
        def __init__(self):
            self.store = Gtk.ListStore(str, GObject.TYPE_PYOBJECT, bool)
            super(Tree, self).__init__()
            self.set_model(self.store)
            self.set_headers_visible(True)

            self.append_column(Gtk.TreeViewColumn('First', Gtk.CellRendererText(), text=0))
            self.append_column(Gtk.TreeViewColumn('Second', CellRendererWidget(lambda widget: '<b>' + widget.get_children()[0].get_label() + '</b>'), widget=1))

        def insert(self, name):
            iter = self.store.append()
            hb = Gtk.HBox()
            hb.pack_start(Gtk.Button(name, True, True, 0))
            lbl = Gtk.Label(label=(name + ' ') * 20)
            lbl.set_line_wrap(True)
            hb.pack_start(lbl, False, True, 0)
            self.store.set(iter, 0, name, 1, hb, 2, True)

    w = Gtk.Window()
    w.set_position(Gtk.WindowPosition.CENTER)
    w.connect('delete-event', Gtk.main_quit)
    t = Tree()
    t.insert('foo')
    t.insert('bar')
    t.insert('baz')
    w.add(t)

    w.show_all()
    Gtk.main()
