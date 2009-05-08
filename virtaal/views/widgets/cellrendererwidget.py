#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import pango
from gobject import PARAM_READWRITE, SIGNAL_RUN_FIRST, TYPE_PYOBJECT


class CellRendererWidget(gtk.GenericCellRenderer):
    __gtype_name__ = 'CellRendererWidget'
    __gproperties__ = {
        'widget': (TYPE_PYOBJECT, 'Widget', 'The column containing the widget to render', PARAM_READWRITE),
    }


    # INITIALIZERS #
    def __init__(self, strfunc):
        gtk.GenericCellRenderer.__init__(self)
        self.props.mode = gtk.CELL_RENDERER_MODE_EDITABLE

        self.editablemap = {}
        self.strfunc = strfunc
        self.widget = None


    # INTERFACE METHODS #
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_activate(self, *args):
        pass

    def on_get_size(self, widget, cell_area=None):
        print '%s>> on_get_size(cell_area=%s)' % (self.strfunc(self.widget), cell_area)
        height = width = 0
        xpad = ypad = 2

        width = widget.get_toplevel().get_allocation().width
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, width)
        lw, lh = layout.get_pixel_size()

        if self.widget in self.editablemap:
            w, h = self.editablemap[self.widget].get_size_request()
            height = max(lh, h)

        height += ypad * 2
        width  += xpad * 2

        return xpad, ypad, width, height

    def on_render(self, window, widget, bg_area, cell_area, expose_area, flags):
        print '%s>> on_render(flags=%s)' % (self.strfunc(self.widget), self.flagstr(flags))
        if flags & gtk.CELL_RENDERER_SELECTED:
            print self.activate(gtk.gdk.Event(gtk.gdk.NOTHING), widget, '', bg_area, cell_area, flags)
            if self.widget in self.editablemap:
                self.editablemap[self.widget].start_editing(gtk.gdk.Event(gtk.gdk.NOTHING))
            return True
        xo, yo, w, h = self.get_size(widget, cell_area)
        x = cell_area.x + xo
        y = cell_area.y + yo
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, w)
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, cell_area, widget, '', x, y, layout)

    def on_start_editing(self, event, tree_view, path, bg_area, cell_area, flags):
        print '%s>> on_start_editing(flags=%s, event=%s)' % (self.strfunc(self.widget), self.flagstr(flags), event)
        if self.widget not in self.editablemap:
            self.editablemap[self.widget] = CellWidget(self.widget)
        self.editablemap[self.widget].set_size_request(cell_area.width, cell_area.height)
        self.editablemap[self.widget].show_all()
        return self.editablemap[self.widget]

    # METHODS #
    def create_pango_layout(self, string, widget, width):
        layout = pango.Layout(widget.get_pango_context())
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_width(width * pango.SCALE)
        layout.set_text(string)
        return layout

    def flagstr(self, flags):
        fset = []
        for f in dir(gtk):
            if not f.startswith('CELL_RENDERER_'):
                continue
            if flags & getattr(gtk, f):
                fset.append(f)
        return '|'.join(fset)


class CellWidget(gtk.HBox, gtk.CellEditable):
    __gtype_name__ = 'CellWidget'
    __gsignals__ = {
        'modified': (SIGNAL_RUN_FIRST, None, ())
    }

    # INITIALIZERS #
    def __init__(self, *widgets):
        super(CellWidget, self).__init__()
        for w in widgets:
            if w.parent is not None:
                w.parent.remove(w)
            self.pack_start(w)


    # INTERFACE METHODS #
    def do_editing_done(self, *args):
        pass

    def do_remove_widget(self, *args):
        pass

    def do_start_editing(self, *args):
        pass


if __name__ == "__main__":
    class Tree(gtk.TreeView):
        def __init__(self):
            self.store = gtk.ListStore(str, TYPE_PYOBJECT, bool)
            gtk.TreeView.__init__(self)
            self.set_model(self.store)
            self.set_headers_visible(True)

            self.append_column(gtk.TreeViewColumn('First', gtk.CellRendererText(), text=0))
            self.append_column(gtk.TreeViewColumn('Second', CellRendererWidget(lambda widget: widget.get_label()), widget=1))

        def insert(self, name):
            iter = self.store.append()
            self.store.set(iter, 0, name, 1, gtk.Button(name), 2, True)

    w = gtk.Window()
    w.set_position(gtk.WIN_POS_CENTER)
    w.connect('delete-event', gtk.main_quit)
    t = Tree()
    t.insert('foo')
    t.insert('bar')
    t.insert('baz')
    w.add(t)

    w.show_all()
    gtk.main()
