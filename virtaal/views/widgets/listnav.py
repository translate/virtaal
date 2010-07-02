#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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

"""
ListNavigator: A composite widget for navigating in a list of "states" by using
"previous" and "next" buttons as well as a pop-up list containing all available
options.
"""

import logging
import gobject, gtk

from popupwidgetbutton import PopupWidgetButton


class ListNavigator(gtk.HBox):
    __gtype_name__ = 'ListNavigator'
    __gsignals__ = {
        'back-clicked':      (gobject.SIGNAL_RUN_FIRST, None, ()),
        'forward-clicked':   (gobject.SIGNAL_RUN_FIRST, None, ()),
        'selection-changed': (gobject.SIGNAL_RUN_FIRST, None, (object,))
    }

    COL_DISPLAY, COL_VALUE = range(2)

    # INITIALIZERS #
    def __init__(self):
        super(ListNavigator, self).__init__()
        self._init_widgets()

    def _init_treeview(self):
        tvw = gtk.TreeView()
        tvw.append_column(gtk.TreeViewColumn(
            "State", gtk.CellRendererText(), text=self.COL_DISPLAY
        ))
        lst = gtk.ListStore(str, object)
        tvw.set_model(lst)
        tvw.set_headers_visible(False)
        tvw.get_selection().connect('changed', self._on_selection_changed)

        return tvw, lst

    def _init_widgets(self):
        # Create widgets
        self.btn_back = gtk.Button()
        self.btn_forward = gtk.Button()
        self.btn_back.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        self.btn_forward.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))

        self.tvw_items, self.lst_items = self._init_treeview()

        self.btn_popup = PopupWidgetButton(self.tvw_items, label='current')

        # Connect to signals
        self.btn_back.connect('clicked', self._on_back_clicked)
        self.btn_forward.connect('clicked', self._on_forward_clicked)

        self.btn_popup.connect('key-press-event', self._on_popup_key_press_event)

        # Add widgets to containers
        self.pack_start(self.btn_back,    expand=False, fill=False)
        self.pack_start(self.btn_popup,   expand=True,  fill=True)
        self.pack_start(self.btn_forward, expand=False, fill=False)


    # METHODS #
    def move_state(self, offset):
        # XXX: Adapted from ActivityEntry._on_key_press_event
        #      (from the hamster-applet project)
        cursor = self.tvw_items.get_cursor()

        if not cursor or not cursor[0]:
            self.tvw_items.set_cursor(0)
            return

        i = cursor[0][0] + offset

        # keep it in the sane borders
        i = min(max(i, 0), len(self.tvw_items.get_model()) - 1)

        self.tvw_items.set_cursor(i)
        self.tvw_items.scroll_to_cell(i, use_align=True, row_align=0.4)

    def set_model(self, model, select_first=True, select_name=None):
        """Set the model for the C{gtk.TreeView} in the pop-up window.
            @type  select_first: bool
            @param select_first: Whether or not the first row should be selected
            @type  select_name: str
            @param select_name: The row with this display value is selected.
                This overrides C{select_first}."""
        if model.get_column_type(self.COL_DISPLAY) != gobject.TYPE_STRING:
            raise ValueError('Column %d does not contain "string" values' % (self.COL_DISPLAY))
        if model.get_column_type(self.COL_VALUE) != gobject.TYPE_PYOBJECT:
            raise ValueError('Column %d does not contain "object" values' % (self.COL_VALUE))

        self.tvw_items.set_model(model)

        select_path = None
        if select_first:
            select_path = 0
        if select_name is not None:
            for row in model:
                if row[self.COL_DISPLAY] == select_name:
                    select_path = row.path
                    break

        if select_path is not None:
            self.tvw_items.set_cursor(select_path)
            self.tvw_items.scroll_to_cell(select_path, use_align=True, row_align=0.4)

    def set_parent_window(self, wnd_parent):
        self.btn_popup.popup.set_transient_for(wnd_parent)

    def select_by_name(self, name):
        for row in self.tvw_items.get_model():
            if row[self.COL_DISPLAY] == name:
                logging.debug('name: %s' % (name))
                self.tvw_items.get_selection().select_iter(row.iter)
                return

    def select_by_object(self, obj):
        for row in self.tvw_items.get_model():
            if row[self.COL_VALUE] == obj:
                self.tvw_items.get_selection().select_iter(row.iter)
                return


    # EVENT HANDLERS #
    def _on_back_clicked(self, button):
        self.emit('back-clicked')
        self.move_state(-1)

    def _on_forward_clicked(self, button):
        self.emit('forward-clicked')
        self.move_state(1)

    def _on_popup_key_press_event(self, widget, event):
        assert widget is self.btn_popup

        # See virtaal.views.widgets.textbox.TextBox._on_key_pressed for an
        # explanation fo the filter below.
        filtered_state = event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK | gtk.gdk.MOD4_MASK | gtk.gdk.SHIFT_MASK)
        keyval = event.keyval

        if filtered_state == 0:
            # No modifying keys (like Ctrl and Alt) are pressed
            if keyval == gtk.keysyms.Up and self.btn_popup.is_popup_visible:
                self.move_state(-1)
                return True
            elif keyval == gtk.keysyms.Down and self.btn_popup.is_popup_visible:
                self.move_state(1)
                return True

        return False

    def _on_selection_changed(self, selection):
        model, itr = selection.get_selected()
        if not model or not itr:
            return
        selected_value = model.get_value(itr, self.COL_VALUE)
        # Disable back/forward buttons if the first/last item was selected
        isfirst = selected_value == model.get_value(model[0].iter, self.COL_VALUE)
        islast  = selected_value == model.get_value(model[len(model)-1].iter, self.COL_VALUE)
        self.btn_back.set_sensitive(not isfirst)
        self.btn_forward.set_sensitive(not islast)

        self.emit('selection-changed', selected_value)


if __name__ == '__main__':
    # XXX: Uncomment below to test RTL
    #gtk.widget_set_default_direction(gtk.TEXT_DIR_RTL)
    listnav = ListNavigator()

    hb = gtk.HBox()
    hb.pack_start(listnav, expand=False, fill=False)
    vb = gtk.VBox()
    vb.pack_start(hb, expand=False, fill=False)

    wnd = gtk.Window()
    wnd.set_title('List Navigator Test')
    wnd.set_size_request(400, 300)
    wnd.add(vb)
    wnd.connect('destroy', lambda *args: gtk.main_quit())
    listnav.set_parent_window(wnd)

    def on_selection_changed(sender, selected):
        sender.btn_popup.set_label('Item %d' % (selected.i))
    listnav.connect('selection-changed', on_selection_changed)

    def create_test_model():
        class Item(object):
            def __init__(self, i):
                self.i = i
            def __str__(self):
                return '<Item i=%s>' % (self.i)

        lst = gtk.ListStore(str, object)
        for i in range(10):
            lst.append([i, Item(i)])
        return lst
    listnav.set_model(create_test_model())

    wnd.show_all()
    gtk.main()
