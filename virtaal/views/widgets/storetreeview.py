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

from gi.repository import GObject
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

        # GObject.timeout_add() id for the pending debounced
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
        # on_configure_event()'s debounce timer outlives a single event,
        # so it needs to be cancelled explicitly on teardown - otherwise
        # a pending GObject.timeout_add() can fire after this widget is
        # destroyed and call back into it (self.get_cursor() etc. on a
        # dead widget). This app already has one known, reproducible
        # teardown-related segfault (GTK widget-hierarchy teardown
        # racing CPython's cyclic GC - see the run-virtaal skill's
        # Gotchas); not adding to that risk.
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
        # FIXED sizing tied to the treeview's own real allocated width
        # (via _on_size_allocate() below), not set_expand(True)'s
        # natural-size renegotiation: on some GTK3 builds (confirmed on
        # Windows/gvsbuild) that renegotiation recomputes a slightly
        # wider value on every reallocation, including ones caused by
        # correcting a previous over-grown size - an unbounded growth
        # loop. FIXED sizing sets the width explicitly and
        # deterministically from the treeview's real allocation instead
        # of letting GTK derive it from cell content.
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(1)  # corrected on the first real size-allocate
        return column

    def _on_size_allocate(self, _widget, allocation):
        # Keeps the FIXED-sizing column's width tied to the treeview's
        # own real allocated width - see _make_column() for why
        # set_expand(True) was replaced with this. A few pixels of
        # margin avoids a vertical scrollbar (if one appears) fighting
        # the column for the same space it just claimed. Guarded on the
        # width actually changing so this doesn't itself queue a
        # pointless reallocation on every single size-allocate,
        # including ones this same call just caused.
        column = self.get_columns()[0] if self.get_columns() else None
        if not column:
            return
        new_width = max(1, allocation.width - 2)
        if column.get_fixed_width() != new_width:
            column.set_fixed_width(new_width)


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
            # Deliberately doesn't force a Gtk.main_iteration() flush after
            # this: doing so from inside select_index() re-entered
            # UnitView.load_unit()/disable_signals()'s signal-blocking
            # window at an unexpected point, spuriously marking a
            # just-opened file as modified.
            self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
            self.get_model().set_editable(newpath)
            # change_cursor() below is deferred via GObject.idle_add(), so
            # it can run after the file has since been closed and a
            # different one opened - guard against re-running set_cursor()
            # against a path/model that's no longer current, which could
            # start editing an arbitrary unit in the new file and
            # spuriously mark it modified.
            scheduled_model = model
            def change_cursor():
                self._waiting_for_row_change -= 1
                if self.get_model() is not scheduled_model:
                    return
                self.set_cursor(newpath, self.get_columns()[0], start_editing=True)
            self._waiting_for_row_change += 1
            GObject.idle_add(change_cursor, priority=GObject.PRIORITY_DEFAULT_IDLE)

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
        # Debounced rather than acted on directly: restoring cursor state
        # on every single raw configure-event tick during a live resize
        # drag is wasteful, and debouncing costs nothing on a healthy
        # resize. The actual column-growth bug this used to chase is
        # fixed at its source in _make_column() (FIXED sizing); this is
        # just settle-then-restore-cursor housekeeping now.
        logging.debug("storetreeview: configure-event %dx%d", event.width, event.height)
        if self._configure_timeout_id is not None:
            GObject.source_remove(self._configure_timeout_id)
        self._configure_timeout_id = GObject.timeout_add(200, self._on_configure_settled)
        return False

    def _on_configure_settled(self):
        self._configure_timeout_id = None
        logging.debug("storetreeview: debounce settled, window=%s", self._window_size())
        self._restore_cursor()
        return False  # one-shot: don't repeat this GObject.timeout_add

    def _on_destroy(self, _widget):
        if self._configure_timeout_id is not None:
            GObject.source_remove(self._configure_timeout_id)
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
        # Deliberately does no corrective resizing or cursor work of its
        # own: GTK's size-allocate cycle handles column width (see
        # _on_size_allocate()) and select_index() handles cursor/editing
        # restoration on its own triggers (navigation, file load). This
        # is just a safety-net check - if the window is ever unexpectedly
        # wide after a resize/focus settle, log it rather than silently
        # resize() it (a reactive resize() here is what caused the
        # original runaway-growth bug this whole area exists to avoid).
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
        # tasks, hence the GObject.idle_add. If we don't wait, then the TreeView
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

        GObject.idle_add(do_scroll)
        return True

    def _on_key_press(self, _widget, _event, _data=None):
        # The TreeView does interesting things with combos like SHIFT+TAB.
        # So we're going to stop it from doing this.
        return True

    def _on_modified(self, _widget):
        self.emit("modified")
        return True
