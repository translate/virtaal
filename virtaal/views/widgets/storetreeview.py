#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
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

import gtk
import gobject
import logging

from storecellrenderer import StoreCellRenderer
from storetreemodel import COLUMN_NOTE, COLUMN_UNIT, COLUMN_EDITABLE, StoreTreeModel


class StoreTreeView(gtk.TreeView):
    """
    The extended C{gtk.TreeView} we use display our units.
    This class was adapted from the old C{UnitGrid} class.
    """

    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    # INITIALIZERS #
    def __init__(self, view):
        self.view = view
        super(StoreTreeView, self).__init__()

        self.set_headers_visible(False)
        #self.set_direction(gtk.TEXT_DIR_LTR)

        self.renderer = self._make_renderer()
        self.append_column(self._make_column(self.renderer))
        self._enable_tooltips()

        self._install_callbacks()

        # This must be changed to a mutex if you ever consider
        # writing multi-threaded code. However, the motivation
        # for this horrid little variable is so dubious that you'd
        # be better off writing better code. I'm sorry to leave it
        # to you.
        self._waiting_for_row_change = 0

    def _enable_tooltips(self):
        if hasattr(self, "set_tooltip_column"):
            self.set_tooltip_column(COLUMN_NOTE)
        self.set_rules_hint(True)

    def _install_callbacks(self):
        self.connect('key-press-event', self._on_key_press)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("button-press-event", self._on_button_press)
        self.connect('focus-in-event', self.on_configure_event)

        # The following connections are necessary, because Gtk+ apparently *only* uses accelerators
        # to add pretty key-bindings next to menu items and does not really care if an accelerator
        # path has a connected handler.
        mainview = self.view.controller.main_controller.view
        mainview.gui.get_widget('mnu_up').connect('activate', lambda *args: self._move_up(None, None, None, None))
        mainview.gui.get_widget('mnu_down').connect('activate', lambda *args: self._move_down(None, None, None, None))
        mainview.gui.get_widget('mnu_pageup').connect('activate', lambda *args: self._move_pgup(None, None, None, None))
        mainview.gui.get_widget('mnu_pagedown').connect('activate', lambda *args: self._move_pgdown(None, None, None, None))

    def _make_renderer(self):
        renderer = StoreCellRenderer(self.view)
        renderer.connect("editing-done", self._on_cell_edited, self.get_model())
        renderer.connect("modified", self._on_modified)
        return renderer

    def _make_column(self, renderer):
        column = gtk.TreeViewColumn(None, renderer, unit=COLUMN_UNIT, editable=COLUMN_EDITABLE)
        column.set_expand(True)
        return column


    # METHODS #
    def select_index(self, index):
        """Select the row with the given index."""
        model = self.get_model()
        if not model or not isinstance(model, StoreTreeModel):
            return
        newpath = model.store_index_to_path(index)
        selected = self.get_selection().get_selected()
        selected_path = isinstance(selected[1], gtk.TreeIter) and model.get_path(selected[1]) or None

        if selected[1] is None or (selected_path and selected_path != newpath):
            #logging.debug('select_index()->self.set_cursor(path="%s")' % (newpath))
            # XXX: Both of the "self.set_cursor()" calls below are necessary in
            #      order to have both bug 869 fixed and keep search highlighting
            #      in working order. After exhaustive inspection of the
            #      interaction between emitted signals involved, Friedel and I
            #      still have no idea why exactly it is needed. This just seems
            #      to be the correct GTK black magic incantation to make it
            #      "work".
            self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
            self.get_model().set_editable(newpath)
            def change_cursor():
                self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
                self._waiting_for_row_change -= 1
            self._waiting_for_row_change += 1
            gobject.idle_add(change_cursor, priority=gobject.PRIORITY_DEFAULT_IDLE)

    def set_model(self, storemodel):
        if storemodel:
            model = StoreTreeModel(storemodel)
        else:
            model = gtk.ListStore(object)
        super(StoreTreeView, self).set_model(model)

    def _keyboard_move(self, offset):
        if not self.view.controller.get_store():
            return

        # We don't want to process keyboard move events until we have finished updating
        # the display after a move event. So we use this awful, awful, terrible scheme to
        # keep track of pending draw events. In reality, it should be impossible for
        # self._waiting_for_row_change to be larger than 1, but my superstition led me
        # to be safe about it.
        if self._waiting_for_row_change > 0:
            return True

        try:
            #self._owner.set_statusbar_message(self.document.mode_cursor.move(offset))
            self.view.cursor.move(offset)
        except IndexError:
            pass

        return True

    def _move_up(self, _accel_group, _acceleratable, _keyval, _modifier):
        return self._keyboard_move(-1)

    def _move_down(self, _accel_group, _acceleratable, _keyval, _modifier):
        return self._keyboard_move(1)

    def _move_pgup(self, _accel_group, _acceleratable, _keyval, _modifier):
        return self._keyboard_move(-10)

    def _move_pgdown(self, _accel_group, _acceleratable, _keyval, _modifier):
        return self._keyboard_move(10)


    # EVENT HANDLERS #
    def _on_button_press(self, widget, event):
        # If the event did not happen in the treeview, but in the
        # editing widget, then the event window will not correspond to
        # the treeview's drawing window. This happens when the
        # user clicks on the edit widget. But if this happens, then
        # we don't want anything to happen, so we return True.
        if event.window != widget.get_bin_window():
            return True

        answer = self.get_path_at_pos(int(event.x), int(event.y))
        if answer is None:
            logging.debug("Not path found at (%d,%d)" % (int(event.x), int(event.y)))
            return True

        old_path, _old_column = self.get_cursor()
        path, _column, _x, _y = answer
        if old_path != path:
            index = self.get_model().path_to_store_index(path)
            if index not in self.view.cursor.indices:
                self.view.controller.main_controller.mode_controller.select_default_mode()
            self.view.cursor.index = index

        return True

    def _on_cell_edited(self, _cell, _path_string, must_advance, _modified, _model):
        if must_advance:
            return self._keyboard_move(1)
        return True

    def on_configure_event(self, widget, _event, *_user_args):
        path, column = self.get_cursor()

        self.columns_autosize()
        if path != None:
            cell_area = self.get_cell_area(path, column)
            def do_setcursor():
                self.set_cursor(path, column, start_editing=True)
            gobject.idle_add(do_setcursor)

        return False

    def _on_cursor_changed(self, _treeview):
        path, _column = self.get_cursor()

        index = _treeview.get_model().path_to_store_index(path)
        if index != self.view.cursor.index:
            self.view.cursor.index = index

        # We defer the scrolling until GTK has finished all its current drawing
        # tasks, hence the gobject.idle_add. If we don't wait, then the TreeView
        # draws the editor widget in the wrong position. Presumably GTK issues
        # a redraw event for the editor widget at a given x-y position and then also
        # issues a TreeView scroll; thus, the editor widget gets drawn at the wrong
        # position.
        def do_scroll():
            self.scroll_to_cell(path, self.get_column(0), True, 0.5, 0.0)
            return False

        gobject.idle_add(do_scroll)
        return True

    def _on_key_press(self, _widget, _event, _data=None):
        # The TreeView does interesting things with combos like SHIFT+TAB.
        # So we're going to stop it from doing this.
        return True

    def _on_modified(self, _widget):
        self.emit("modified")
        return True
