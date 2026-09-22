#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Pango
from gi.repository.GObject import TYPE_PYOBJECT, ParamFlags, SignalFlags

PARAM_READWRITE = ParamFlags.READWRITE
SIGNAL_RUN_FIRST = SignalFlags.RUN_FIRST


class CellRendererWidget(Gtk.CellRenderer):
    __gtype_name__ = 'CellRendererWidget'
    __gproperties__ = {
        'widget': (TYPE_PYOBJECT, 'Widget', 'The column containing the widget to render', PARAM_READWRITE),
    }

    XPAD = 2
    YPAD = 2


    # INITIALIZERS #
    def __init__(self, strfunc, default_width=-1, widget_func=None):
        super().__init__()

        self.default_width = default_width
        self.strfunc = strfunc
        self.widget = None
        self.widget_func = widget_func or (lambda item: None)
        self.props.mode = Gtk.CellRendererMode.EDITABLE


    # INTERFACE METHODS #
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_size(self, widget, cell_area=None):
        if cell_area is not None:
            return self.XPAD, self.YPAD, cell_area.width - 2*self.XPAD, cell_area.height - 2*self.YPAD

        width = widget.get_allocation().width
        if width <= 1:
            width = self.default_width
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, width)
        width, height = layout.get_pixel_size()

        if self.widget:
            requisition = self.widget.size_request()
            w = requisition.width
            h = requisition.height
            width =  max(width,  w)
            height = max(height, h)

        height += self.YPAD * 2
        width  += self.XPAD * 2

        return self.XPAD, self.YPAD, width, height

    def do_render(self, window, widget, bg_area, cell_area, flags):
        if flags & Gtk.CellRendererState.SELECTED:
            if self.props.editing == True:
                # the widget will render itself
                return

        x = cell_area.x + self.XPAD
        y = cell_area.y + self.YPAD
        w = cell_area.width - 2 * self.XPAD
        h = cell_area.height - 2 * self.YPAD
        layout = self.create_pango_layout(self.strfunc(self.widget), widget, w)
        layout_w, layout_h = layout.get_pixel_size()
        y = y + (h-layout_h)/2
        Gtk.render_layout(
            context=widget.get_style_context(),
            cr=window,
            x=x,
            y=y,
            layout=layout
        )

    def do_start_editing(self, event, treeview, path, bg_area, cell_area, flags):
        model = treeview.get_model()
        itr = model.get_iter(path)
        item = treeview.get_item(itr)
        widget = self.widget_func(item)
        if widget and "config" in item:
            editable = CellWidget(widget)
            editable.show_all()
            editable.grab_focus()
            #TODO: focus the button
            return editable

    # METHODS #
    def create_pango_layout(self, string, widget, width):
        font = widget.get_pango_context().get_font_description()
        layout = Pango.Layout(widget.get_pango_context())
        layout.set_font_description(font)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_width(width * Pango.SCALE)
        layout.set_markup(string)
        # This makes no sense, but mostly has the desired effect to align things correctly for
        # RTL languages which is otherwise incorrect. Untranslated entries is still wrong.
        if widget.get_direction() == Gtk.TextDirection.RTL:
            layout.set_alignment(Pango.Alignment.RIGHT)
            layout.set_auto_dir(False)
        return layout


class CellWidget(Gtk.HBox, Gtk.CellEditable):
    __gtype_name__ = 'CellWidget'
    __gsignals__ = {
        'modified': (SIGNAL_RUN_FIRST, None, ())
    }
    __gproperties__ = {
        'editing-canceled': (bool, 'Editing cancelled', 'Editing was cancelled', False, PARAM_READWRITE),
    }

    # INITIALIZERS #
    def __init__(self, *widgets):
        super().__init__()
        for w in widgets:
            if w.get_parent() is not None:
                w.get_parent().remove(w)
            self.pack_start(w, True, True, 0)


    # INTERFACE METHODS #
    def do_editing_done(self, *args):
        pass

    def do_remove_widget(self, *args):
        pass

    def do_start_editing(self, *args):
        pass
