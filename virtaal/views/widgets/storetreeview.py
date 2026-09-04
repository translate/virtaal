#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
# Copyright 2016 F Wolff
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

import logging

from gi.repository import GLib, GObject
from gi.repository import Gtk

from .storecellrenderer import StoreCellRenderer
from .storetreemodel import COLUMN_NOTE, COLUMN_UNIT, COLUMN_EDITABLE, StoreTreeModel


class StoreTreeView(Gtk.TreeView):
    """
    The extended C{Gtk.TreeView} we use display our units.
    This class was adapted from the old C{UnitGrid} class.
    """
    __gtype_name__ = 'StoreTreeView'

    __gsignals__ = {
        'modified': (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    # INITIALIZERS #
    def __init__(self, view):
        self.view = view
        super().__init__()

        self.set_headers_visible(False)
        # self.set_direction(Gtk.TextDirection.LTR)

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

        # GLib.timeout_add() id for the pending debounced
        # on_configure_event() action - see that method for why.
        self._configure_timeout_id = None

    def _enable_tooltips(self):
        if hasattr(self, "set_tooltip_column"):
            self.set_tooltip_column(COLUMN_NOTE)
        self.set_rules_hint(True)

    def _install_callbacks(self):
        self.connect('key-press-event', self._on_key_press)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("button-press-event", self._on_button_press)
        self.connect('focus-in-event', self._on_focus_in)
        # Keeps the FIXED-sizing column's width tied to this treeview's
        # own real allocation - see _make_column() for why this exists.
        self.connect('size-allocate', self._on_size_allocate)
        # Cancel the pending debounce timer on teardown - it would
        # otherwise fire after this widget is destroyed.
        self.connect('destroy', self._on_destroy)

        # The following connections are necessary, because Gtk+ apparently *only* uses accelerators
        # to add pretty key-bindings next to menu items and does not really care if an accelerator
        # path has a connected handler.
        mainview = self.view.controller.main_controller.view
        mainview.gui.get_object('mnu_up').connect('activate', lambda *args: self._move_up(None, None, None, None))
        mainview.gui.get_object('mnu_down').connect('activate', lambda *args: self._move_down(None, None, None, None))
        mainview.gui.get_object('mnu_pageup').connect('activate', lambda *args: self._move_pgup(None, None, None, None))
        mainview.gui.get_object('mnu_pagedown').connect('activate', lambda *args: self._move_pgdown(None, None, None, None))

    def _make_renderer(self):
        renderer = StoreCellRenderer(self.view)
        renderer.connect("editing-done", self._on_cell_edited, self.get_model())
        renderer.connect("modified", self._on_modified)
        return renderer

    def _make_column(self, renderer):
        column = Gtk.TreeViewColumn(None, renderer, unit=COLUMN_UNIT, editable=COLUMN_EDITABLE)
        # FIXED sizing avoids set_expand(True)'s natural-size
        # renegotiation, which could grow the column unboundedly on
        # some GTK3 builds - see _on_size_allocate() for the real width.
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(1)  # corrected on the first real size-allocate
        return column

    def _on_size_allocate(self, _widget, allocation):
        # A couple of pixels of margin avoids fighting a vertical
        # scrollbar for the same space; guarded on an actual change so
        # this doesn't itself trigger another reallocation.
        column = self.get_columns()[0] if self.get_columns() else None
        if not column:
            return
        new_width = max(1, allocation.width - 2)
        if column.get_fixed_width() != new_width:
            column.set_fixed_width(new_width)

    def reset_column_width(self):
        """Relax the FIXED-width column back to its placeholder size
        (see _make_column()), letting the next size-allocate correct
        it for real. A FIXED-width column's current width becomes part
        of the toplevel window's own effective minimum size - confirmed
        live: main_window.resize() to a smaller size was silently
        clamped back up, unchanged, while this column still held its
        fullscreen-era width. Called right before a resize() that needs
        to shrink the window past whatever width this column is
        currently holding (F11 fullscreen exit is the real case)."""
        column = self.get_columns()[0] if self.get_columns() else None
        if column:
            column.set_fixed_width(1)


    # METHODS #
    def select_index(self, index):
        """Select the row with the given index."""
        model = self.get_model()
        if not model or not isinstance(model, StoreTreeModel):
            return
        newpath = Gtk.TreePath(model.store_index_to_path(index))
        selected = self.get_selection().get_selected()
        selected_path = isinstance(selected[1], Gtk.TreeIter) and model.get_path(selected[1]) or None

        if selected[1] is None or (selected_path and selected_path != newpath):
            #logging.debug('select_index()->self.set_cursor(path="%s")' % (newpath))
            # XXX: Both of the "self.set_cursor()" calls below are necessary in
            #      order to have both bug 869 fixed and keep search highlighting
            #      in working order. After exhaustive inspection of the
            #      interaction between emitted signals involved, Friedel and I
            #      still have no idea why exactly it is needed. This just seems
            #      to be the correct GTK black magic incantation to make it
            #      "work".
            #
            # No Gtk.main_iteration() flush here - it re-entered
            # UnitView.load_unit()'s signal-blocking window and
            # spuriously marked a just-opened file modified.
            self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
            self.get_model().set_editable(newpath)
            # Guard against change_cursor() below (deferred via idle_add)
            # running after a different file's model is now current.
            scheduled_model = model
            def change_cursor():
                self._waiting_for_row_change -= 1
                if self.get_model() is not scheduled_model:
                    return
                self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
            self._waiting_for_row_change += 1
            GLib.idle_add(change_cursor, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def set_model(self, storemodel):
        if storemodel:
            model = StoreTreeModel(storemodel)
        else:
            model = None
        super().set_model(model)

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

    def on_configure_event(self, widget, event, *_user_args):
        # Debounced - restoring cursor state on every raw configure-event
        # tick during a live resize drag is wasteful. The growth bug
        # itself is fixed at the source (_make_column()); this is just
        # settle-then-restore-cursor housekeeping.
        logging.debug("storetreeview: configure-event %dx%d", event.width, event.height)
        if self._configure_timeout_id is not None:
            GLib.source_remove(self._configure_timeout_id)
        self._configure_timeout_id = GLib.timeout_add(200, self._on_configure_settled)
        return False

    def _on_configure_settled(self):
        self._configure_timeout_id = None
        logging.debug("storetreeview: debounce settled, window=%s", self._window_size())
        self._restore_cursor()
        return False  # one-shot: don't repeat this GLib.timeout_add

    def _on_destroy(self, _widget):
        if self._configure_timeout_id is not None:
            GLib.source_remove(self._configure_timeout_id)
            self._configure_timeout_id = None

    def _on_focus_in(self, widget, _event, *_user_args):
        # Restore cursor/editing state on refocus, same as
        # on_configure_event()'s settle handler.
        self._restore_cursor()
        return False

    def _window_size(self):
        window = self.get_toplevel()
        if window and isinstance(window, Gtk.Window) and window.get_realized():
            return window.get_size()
        return None

    def _restore_cursor(self):
        # Safety-net check only, no corrective action: a reactive
        # resize() here is what caused the original growth bug.
        size = self._window_size()
        if size and size[0] > 1024:
            logging.warning("storetreeview: window width %d after a resize/focus settle - investigate if seen again", size[0])

    def _on_cursor_changed(self, _treeview):
        path, _column = self.get_cursor()

        model = _treeview.get_model()
        if not model:
            return True

        index = model.path_to_store_index(path)
        if self.view.cursor and index != self.view.cursor.index:
            self.view.cursor.index = index

        # We defer the scrolling until GTK has finished all its current drawing
        # tasks, hence the GLib.idle_add. If we don't wait, then the TreeView
        # draws the editor widget in the wrong position. Presumably GTK issues
        # a redraw event for the editor widget at a given x-y position and then also
        # issues a TreeView scroll; thus, the editor widget gets drawn at the wrong
        # position.
        def do_scroll():
            if not self.get_cursor()[0]:
                # cursor became invalid since this was added to the idle queue
                # maybe because the file was closed since then.
                return False
            if path:
                self.scroll_to_cell(path, self.get_column(0), True, 0.5, 0.0)
            return False

        GLib.idle_add(do_scroll)
        return True

    def _on_key_press(self, _widget, _event, _data=None):
        # The TreeView does interesting things with combos like SHIFT+TAB.
        # So we're going to stop it from doing this.
        return True

    def _on_modified(self, _widget):
        self.emit("modified")
        return True
