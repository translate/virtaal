#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging

from gi.repository import GLib, GObject, Gtk

from .storecellrenderer import StoreCellRenderer
from .storetreemodel import COLUMN_EDITABLE, COLUMN_UNIT, StoreTreeModel


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

        # See StoreCellRenderer.do_get_size()'s own comment - True for
        # the duration of a live resize (first configure-event to
        # debounce-settled), used there to skip expensive per-allocate
        # editor-height remeasurement until the resize actually stops.
        self.is_resizing = False

        # Throttles rapid key-repeat navigation - see _keyboard_move() (#3805).
        self._pending_move_offset = 0
        self._move_throttle_id = None

        # id(unit) of every row StoreCellRenderer last gave an estimated
        # (not exact) height - see _revalidate_visible_estimated_rows().
        self._estimated_unit_ids = set()
        self._visible_range_cache = None  # see get_cached_visible_range()
        self._revalidate_scheduled = False
        self.connect('notify::vadjustment', self._on_vadjustment_notify)

    def _install_callbacks(self):
        self.connect('key-press-event', self._on_key_press)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("button-press-event", self._on_button_press)
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
        # some GTK3 builds - see do_size_allocate() for the real width.
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(1)  # corrected on the first real size-allocate
        return column

    def do_size_allocate(self, allocation):
        # Keeps the FIXED column's width tied to this treeview's own
        # allocation (see _make_column()). Set before chaining up, so
        # this allocation already lays it out at the new width.
        changed = self._set_column_width(allocation.width)
        Gtk.TreeView.do_size_allocate(self, allocation)
        self._on_size_allocate(changed)

    def _set_column_width(self, width):
        """@returns: whether the column's width changed."""
        # A couple of pixels of margin avoids fighting a vertical
        # scrollbar for the same space; guarded on an actual change so
        # this doesn't itself trigger another reallocation.
        column = self.get_columns()[0] if self.get_columns() else None
        if not column:
            return False
        new_width = max(1, width - 2)
        if column.get_fixed_width() == new_width:
            return False
        column.set_fixed_width(new_width)
        return True

    def _on_size_allocate(self, width_changed):
        # A mid-drag cell_area here is intermediate, not final -
        # defer to _on_configure_settled()'s own restore (#3595).
        if width_changed:
            if self.is_resizing:
                return
            path, editcol = self.get_cursor()
            if path is not None:
                self._restart_editing(path, editcol or self.get_columns()[0])
        self._schedule_revalidate_visible_estimated_rows()

    def _on_vadjustment_notify(self, _widget, _pspec):
        # Only assigned once this treeview is inside a Gtk.ScrolledWindow
        # (StoreView.show()), not yet at construction time.
        vadjustment = self.props.vadjustment
        if vadjustment:
            vadjustment.connect('value-changed', self._on_vscroll)

    def _on_vscroll(self, _adjustment):
        self._schedule_revalidate_visible_estimated_rows()

    def mark_row_estimated(self, unit):
        self._estimated_unit_ids.add(id(unit))

    def mark_row_measured_exactly(self, unit):
        self._estimated_unit_ids.discard(id(unit))

    def get_cached_visible_range(self):
        """The (start_index, end_index) pair get_visible_range() last
        returned, or None. StoreCellRenderer reads this instead of
        calling get_visible_range() itself - do_get_size() is called
        *by* GTK's own row-height validation, and get_visible_range()
        depends on that same in-progress row-height state, so calling
        it back from there is an unsafe reentrant call. This is only
        ever refreshed from a safe, non-reentrant context - a real
        size-allocate or scroll."""
        return self._visible_range_cache

    def _schedule_revalidate_visible_estimated_rows(self):
        # Deferred, not run synchronously from the caller - this can
        # change a row's height via model.row_changed(), and so this
        # treeview's own total content height, mutating the very
        # vadjustment whose own 'value-changed' signal may still be
        # mid-dispatch in the scroll case.
        if self._revalidate_scheduled:
            return
        self._revalidate_scheduled = True
        GLib.idle_add(self._do_revalidate_visible_estimated_rows)

    def _do_revalidate_visible_estimated_rows(self):
        self._revalidate_scheduled = False
        self._revalidate_visible_estimated_rows()
        return GLib.SOURCE_REMOVE

    def _revalidate_visible_estimated_rows(self):
        """Refresh the cached visible range, then force GTK to re-query
        the height of any row within the renderer's own near-viewport
        buffer that's still carrying an estimated (not exact) height -
        see StoreCellRenderer._row_needs_exact_height(). Without the
        re-query, a row scrolled into view keeps whatever height it was
        last validated at instead of being re-measured on its own."""
        visible_range = self.get_visible_range()
        if visible_range is None:
            self._visible_range_cache = None
        else:
            start, end = visible_range
            self._visible_range_cache = (start.get_indices()[0], end.get_indices()[0])

        if not self._estimated_unit_ids or self._visible_range_cache is None:
            return
        model = self.get_model()
        if not isinstance(model, StoreTreeModel):
            return
        buffer = self.renderer.VIEWPORT_ROW_BUFFER
        start_index = max(0, self._visible_range_cache[0] - buffer)
        end_index = min(model.row_count() - 1, self._visible_range_cache[1] + buffer)
        for row in range(start_index, end_index + 1):
            unit = model.unit_at_row(row)
            if id(unit) in self._estimated_unit_ids:
                path = Gtk.TreePath((row,))
                model.row_changed(path, model.get_iter(path))


    # METHODS #
    def select_index(self, index, force=False):
        """Select the row with the given index.
            @param force: Start editing it even if it is already selected."""
        model = self.get_model()
        if not model or not isinstance(model, StoreTreeModel):
            return
        path = model.store_index_to_path(index)
        if path is None:
            return
        newpath = Gtk.TreePath(path)
        selected = self.get_selection().get_selected()
        selected_path = isinstance(selected[1], Gtk.TreeIter) and model.get_path(selected[1]) or None

        if force or selected[1] is None or (selected_path and selected_path != newpath):
            self._start_editing_cycle(model, newpath)

    def _start_editing_cycle(self, model, path):
        #logging.debug('_start_editing_cycle()->self.set_cursor(path="%s")' % (path))
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
        self.set_cursor(path, self.get_columns()[0], start_editing=True)
        self.get_model().set_editable(path)
        # Guard against change_cursor() below (deferred via idle_add)
        # running after a different file's model is now current.
        scheduled_model = model
        def change_cursor():
            self._waiting_for_row_change -= 1
            if self.get_model() is not scheduled_model:
                return
            self.set_cursor(path, self.get_columns()[0], start_editing=True)
        self._waiting_for_row_change += 1
        GLib.idle_add(change_cursor, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def refresh_current_row(self):
        """Redo the current row's editing cycle in place, without
        changing which row is selected - e.g. after a plugin has
        changed the current unit's rendered content in place (a
        terminology match appearing/disappearing, #3240). select_index()
        skips its own editing cycle when the path hasn't changed, so
        that case has to be driven directly."""
        model = self.get_model()
        if not model or not isinstance(model, StoreTreeModel):
            return
        path, _column = self.get_cursor()
        if path is None:
            return
        self._start_editing_cycle(model, path)

    def set_model(self, storemodel, rows=None):
        self._estimated_unit_ids = set()
        self._visible_range_cache = None
        if storemodel:
            model = StoreTreeModel(storemodel, rows)
        else:
            model = None
        super().set_model(model)

    # Beyond this many rows changing, rebuilding the model is cheaper than
    # a row-inserted/row-deleted signal per row.
    MAX_INCREMENTAL_ROW_CHANGES = 100

    def set_visible_rows(self, rows):
        """Show only the units at the sorted store indices C{rows}, or every
            unit for C{None}.
            @returns: C{None} if nothing changed, else C{'changed'} or, for
                a new model, C{'rebuilt'}. Either way GTK has stopped editing."""
        model = self.get_model()
        if not isinstance(model, StoreTreeModel) or model.visible_rows == rows:
            return None
        if rows is not None:
            rows = list(rows)
        old = model.visible_rows
        if old is None or rows is None:
            changes = abs(model._store_len - len(rows if old is None else old))
        else:
            changes = len(set(old).symmetric_difference(rows))
        if changes <= self.MAX_INCREMENTAL_ROW_CHANGES:
            # GTK moves its own cursor off deleted rows; that isn't a move
            # of the store's cursor.
            self._updating_rows = True
            try:
                model.set_visible_rows(rows)
            finally:
                self._updating_rows = False
            return 'changed'
        editable = model._current_editable
        self.set_model(model._store, rows)
        self.get_model()._current_editable = editable
        return 'rebuilt'

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

        self._pending_move_offset += offset
        if self._move_throttle_id is None:
            # First move of a burst applies immediately; further
            # repeats only accumulate until the next tick (#3805).
            self._apply_pending_move()
            self._move_throttle_id = GLib.timeout_add(50, self._on_move_throttle)

        return True

    def _apply_pending_move(self):
        offset, self._pending_move_offset = self._pending_move_offset, 0
        old_index = self.view.cursor.index
        try:
            self.view.cursor.move(offset)
        except IndexError:
            return
        if offset and old_index >= 0 and self.view.cursor.index == old_index:
            # A navigation list of one: finish the unit anyway, so its
            # workflow state is applied.
            self.view.controller.main_controller.unit_controller.finish_current_unit()
            self.refresh_current_row()

    def _on_move_throttle(self):
        if self._pending_move_offset:
            self._apply_pending_move()
            return True  # keep ticking - more arrived since the last tick
        self._move_throttle_id = None
        return False  # caught up - one-shot until the next burst starts

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
            # A unit outside the mode's list is visited, staying in the mode.
            self.view.cursor.visit(index)

        return True

    def _on_cell_edited(self, _cell, _path_string, must_advance, _modified, _model):
        if must_advance:
            return self._keyboard_move(1)
        return True

    def on_configure_event(self, widget, event, *_user_args):
        # Debounced - restarting editing on every raw configure-event
        # tick during a live resize drag is wasteful.
        logging.debug("storetreeview: configure-event %dx%d", event.width, event.height)
        self.is_resizing = True
        if self._configure_timeout_id is not None:
            GLib.source_remove(self._configure_timeout_id)
        self._configure_timeout_id = GLib.timeout_add(200, self._on_configure_settled)
        return False

    def _on_configure_settled(self):
        self._configure_timeout_id = None
        self.is_resizing = False
        logging.debug("storetreeview: debounce settled, window=%s", self._window_size())
        # do_get_size() was skipping real height recomputation while
        # is_resizing was True (see its own comment) - ask GTK to
        # re-request sizes now that it's settled, so the row(s) it
        # skipped get one real, correct measurement at the final width.
        self.queue_resize()
        # The restore _on_size_allocate() skipped during the drag -
        # unconditional, since the column width may already match (#3595).
        column = self.get_columns()[0] if self.get_columns() else None
        path, editcol = self.get_cursor()
        if column and path is not None:
            self._restart_editing(path, editcol or column)
        return False  # one-shot: don't repeat this GLib.timeout_add

    def _restart_editing(self, path, column):
        """Re-place the editor after a resize, without taking focus from a
            widget outside this tree view, such as the search box."""
        window = self.get_toplevel()
        focus = window.get_focus() if isinstance(window, Gtk.Window) else None
        self.set_cursor(path, column, start_editing=True)
        if focus is None or focus is self or focus.is_ancestor(self) or window.get_focus() is focus:
            return
        if isinstance(focus, Gtk.Entry):
            focus.grab_focus_without_selecting()
        else:
            focus.grab_focus()

    def _on_destroy(self, _widget):
        if self._configure_timeout_id is not None:
            GLib.source_remove(self._configure_timeout_id)
            self._configure_timeout_id = None
        if self._move_throttle_id is not None:
            GLib.source_remove(self._move_throttle_id)
            self._move_throttle_id = None

    def _window_size(self):
        window = self.get_toplevel()
        if window and isinstance(window, Gtk.Window) and window.get_realized():
            return window.get_size()
        return None

    def _on_cursor_changed(self, _treeview):
        if getattr(self, '_updating_rows', False):
            return True
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
