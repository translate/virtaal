#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""
ListNavigator: A composite widget for navigating in a list of "states" by using
"previous" and "next" buttons as well as a pop-up list containing all available
options.
"""

import logging

from gi.repository import Gdk, GObject, Gtk

from .popupwidgetbutton import PopupWidgetButton


class ListNavigator(Gtk.HBox):
    __gtype_name__ = 'ListNavigator'
    __gsignals__ = {
        'back-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'forward-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'selection-changed': (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    COL_DISPLAY, COL_VALUE = range(2)

    # INITIALIZERS #
    def __init__(self):
        super().__init__()
        self.unselectable = []
        self._should_emit_changed = True
        self._init_widgets()

    def _init_treeview(self):
        tvw = Gtk.TreeView()
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("State", renderer, text=self.COL_DISPLAY)
        column.set_cell_data_func(renderer, self._render_item)
        tvw.append_column(column)
        lst = Gtk.ListStore(str, object)
        tvw.set_model(lst)
        tvw.set_headers_visible(False)
        tvw.get_selection().set_select_function(self._may_select)
        tvw.get_selection().connect('changed', self._on_selection_changed)
        tvw.connect('button-release-event', self._on_item_clicked)

        return tvw, lst

    def _init_widgets(self):
        # Create widgets
        self.btn_back = Gtk.Button()
        self.btn_forward = Gtk.Button()
        self.btn_back.add(Gtk.Arrow(arrow_type=Gtk.ArrowType.LEFT, shadow_type=Gtk.ShadowType.NONE))
        self.btn_forward.add(Gtk.Arrow(arrow_type=Gtk.ArrowType.RIGHT, shadow_type=Gtk.ShadowType.NONE))

        self.tvw_items, self.lst_items = self._init_treeview()
        frame = Gtk.Frame()
        # frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        frame.add(self.tvw_items)

        self.btn_popup = PopupWidgetButton(frame, label='(uninitialised)')

        # Connect to signals
        self.btn_back.connect('clicked', self._on_back_clicked)
        self.btn_forward.connect('clicked', self._on_forward_clicked)

        self.btn_popup.connect('key-press-event', self._on_popup_key_press_event)

        # Add widgets to containers
        self.pack_start(self.btn_back, False, False, 0)
        self.pack_start(self.btn_popup, True, True, 0)
        self.pack_start(self.btn_forward, False, False, 0)

    def set_tooltips_text(self, backward, default, forward):
        """Set tooltips for the widgets."""
        self.btn_back.set_tooltip_text(backward)
        self.set_tooltip_text(default)
        self.btn_forward.set_tooltip_text(forward)

    def _is_selectable(self, model, itr):
        return model.get_value(itr, self.COL_DISPLAY) not in self.unselectable

    def _render_item(self, column, renderer, model, itr, data=None):
        renderer.set_property('sensitive', self._is_selectable(model, itr))

    def _may_select(self, selection, model, path, currently_selected, data=None):
        # Unselectable rows (e.g. "Untranslated") can only be selected
        # internally, to show the current state, but can always be left.
        if currently_selected or not self._should_emit_changed:
            return True
        return self._is_selectable(model, model.get_iter(path))

    # METHODS #
    def move_state(self, offset):
        # XXX: Adapted from ActivityEntry._on_key_press_event
        #      (from the hamster-applet project)
        model, itr = self.tvw_items.get_selection().get_selected()
        path = model.get_path(itr)
        i = path[0] + offset
        # keep it in the sane borders
        i = min(max(i, 0), len(self.tvw_items.get_model()) - 1)

        target_itr = model.get_iter(i)
        target_name = model.get_value(target_itr, self.COL_DISPLAY)
        if target_name in self.unselectable:
            return

        self.tvw_items.scroll_to_cell(i, use_align=True, row_align=0.4)
        self.tvw_items.set_cursor(i)

    def set_model(self, model, unselectable=None, select_first=True, select_name=None):
        """Set the model for the C{Gtk.TreeView} in the pop-up window.
            @type  select_first: bool
            @param select_first: Whether or not the first row should be selected
            @type  select_name: str
            @param select_name: The row with this display value is selected.
                This overrides C{select_first}."""
        if model.get_column_type(self.COL_DISPLAY) != GObject.TYPE_STRING:
            raise ValueError('Column %d does not contain "string" values' % (self.COL_DISPLAY))
        if model.get_column_type(self.COL_VALUE) != GObject.TYPE_PYOBJECT:
            raise ValueError('Column %d does not contain "object" values' % (self.COL_VALUE))

        # we're just initialising, so we don't want listeners to think something really changed
        self._should_emit_changed = False
        self.tvw_items.set_model(model)
        if unselectable:
            self.unselectable = unselectable
        else:
            self.unselectable = []

        select_path = None
        if select_first:
            select_path = 0
        if select_name is not None:
            for row in model:
                if row[self.COL_DISPLAY] == select_name:
                    select_path = row.path[0]
                    self.btn_popup.set_label(select_name)
                    break

        if select_path is not None:
            self.tvw_items.set_cursor(select_path)
            self.tvw_items.scroll_to_cell(select_path, use_align=True, row_align=0.4)
        self._should_emit_changed = True

    def set_unselectable(self, unselectable):
        """Change which rows are greyed out and can't be picked."""
        if unselectable == self.unselectable:
            return
        self.unselectable = unselectable
        self.tvw_items.queue_draw()
        model, itr = self.tvw_items.get_selection().get_selected()
        if model and itr:
            self._update_arrows(model, itr)

    def set_parent_window(self, wnd_parent):
        self.btn_popup.popup.set_transient_for(wnd_parent)

    def select_by_name(self, name):
        self._should_emit_changed = False
        for row in self.tvw_items.get_model():
            if row[self.COL_DISPLAY] == name:
                logging.debug('name: %s' % (name))
                self.tvw_items.get_selection().select_iter(row.iter)
                self._should_emit_changed = True
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
        # explanation of the filter below.
        filtered_state = event.get_state() & (
                    Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.MOD4_MASK | Gdk.ModifierType.SHIFT_MASK)
        keyval = event.keyval

        if filtered_state == 0:
            # No modifying keys (like Ctrl and Alt) are pressed
            if keyval == Gdk.KEY_Up and self.btn_popup.is_popup_visible:
                self.move_state(-1)
                return True
            elif keyval == Gdk.KEY_Down and self.btn_popup.is_popup_visible:
                self.move_state(1)
                return True
            elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.btn_popup.is_popup_visible:
                self.btn_popup.hide_popup()
                return True

        return False

    def _on_item_clicked(self, treeview, event):
        hit = treeview.get_path_at_pos(int(event.x), int(event.y))
        model = treeview.get_model()
        if hit is None or self._is_selectable(model, model.get_iter(hit[0])):
            self.btn_popup.hide_popup()
        return False

    def _update_arrows(self, model, itr):
        # Back/forward only where there's a selectable neighbour.
        index = model.get_path(itr)[0]
        self.btn_back.set_sensitive(index > 0 and self._is_selectable(model, model[index - 1].iter))
        self.btn_forward.set_sensitive(
            index < len(model) - 1 and self._is_selectable(model, model[index + 1].iter))

    def _on_selection_changed(self, selection):
        model, itr = selection.get_selected()
        if not model or not itr:
            return
        selected_name  = model.get_value(itr, self.COL_DISPLAY)
        selected_value = model.get_value(itr, self.COL_VALUE)

        self.btn_popup.set_label(selected_name)

        self._update_arrows(model, itr)

        if self._should_emit_changed:
            self.emit('selection-changed', selected_value)
