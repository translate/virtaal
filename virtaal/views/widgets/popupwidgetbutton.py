#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""
PopupWidgetButton: Extends a C{Gtk.ToggleButton} to show a given widget in a
pop-up window.
"""

from gi.repository import Gdk, GLib, GObject, Gtk

# XXX: Kudo's to Toms Bauģis <toms.baugis at gmail.com> who wrote the
#      ActivityEntry widget for the hamster-applet project. A lot of this
#      class's signal handling is based on his example.

# Positioning constants below:
# POS_CENTER_BELOW: Centers the pop-up window below the button (default).
# POS_CENTER_ABOVE: Centers the pop-up window above the button.
# POS_NW_SW: Positions the pop-up window so that its North West (top left)
#            corner is on the South West corner of the button.
# POS_NE_SE: Positions the pop-up window so that its North East (top right)
#            corner is on the South East corner of the button. RTL of POS_NW_SW
# POS_NW_NE: Positions the pop-up window so that its North West (top left)
#            corner is on the North East corner of the button.
# POS_SE_NE: Positions the pop-up window so that its South East (bottom right)
#            corner is on the North East corner of the button.
# POS_SW_NW: Positions the pop-up window so that its South West (bottom left)
#            corner is on the North West corner of the button. RTL of POS_SE_NE

POS_CENTER_BELOW, POS_CENTER_ABOVE, POS_NW_SW, POS_NE_SE, POS_NW_NE, POS_SW_NW, POS_SE_NE = range(7)
# XXX: Add position symbols above as needed and implementation in
#      _update_popup_geometry()

_rtl_pos_map = {
        POS_CENTER_BELOW: POS_CENTER_BELOW,
        POS_CENTER_ABOVE: POS_CENTER_ABOVE,
        POS_SE_NE: POS_SW_NW,
        POS_NW_SW: POS_NE_SE,
}

# Frames to wait for the button to stop moving before showing the pop-up anyway.
MAX_SHOW_TICKS = 10


class PopupWidgetButton(Gtk.ToggleButton):
    """Extends a C{Gtk.ToggleButton} to show a given widget in a pop-up window."""
    __gtype_name__ = 'PopupWidgetButton'
    __gsignals__ = {
        'shown':  (GObject.SignalFlags.RUN_FIRST, None, ()),
        'hidden': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # INITIALIZERS #
    def __init__(self, widget, label='Pop-up', popup_pos=POS_NW_SW, main_window=None, sticky=False):
        super().__init__(label=label)
        if not sticky:
            self.connect('focus-out-event', self._on_focus_out_event)
        if main_window:
            # Hidden while the main window isn't focused, then back.
            main_window.connect('focus-out-event', self._on_main_window_focus_changed, False)
            main_window.connect('focus-in-event', self._on_main_window_focus_changed, True)
        self._main_window_focused = True
        self.connect('key-press-event', self._on_key_press_event)
        self.connect('toggled', self._on_toggled)

        if self.get_direction() == Gtk.TextDirection.LTR:
            self.popup_pos = popup_pos
        else:
            self.popup_pos = _rtl_pos_map.get(popup_pos, POS_NE_SE)
        self._parent_button_press_id = None
        self._update_popup_geometry_func = None
        self._place_popup_id = None
        self._show_tick_id = None
        self._placed_anchor = None

        # Create pop-up window
        self.popup = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.popup.set_size_request(0,0)
        self.popup.add(widget)
        self.popup.show_all()
        self.popup.hide()
        self.popup.connect('check-resize', self._on_popup_check_resize)

        self.connect('draw', self._on_expose)


    # ACCESSORS #
    def _get_is_popup_visible(self):
        return self.popup.props.visible
    is_popup_visible = property(_get_is_popup_visible)

    def set_update_popup_geometry_func(self, func):
        self._update_popup_geometry_func = func

    # METHODS #
    def calculate_popup_xy(self, popup_alloc, btn_alloc, btn_window_xy):
        # Default values are POS_NW_SW
        x = btn_window_xy.x + btn_alloc.x
        y = btn_window_xy.y + btn_alloc.y + btn_alloc.height
        # width, height = self.popup.get_child_requisition()

        if self.popup_pos == POS_NE_SE:
            x -= (popup_alloc.width - btn_alloc.width)
        elif self.popup_pos == POS_NW_NE:
            x += btn_alloc.width
            y = btn_window_xy.y + btn_alloc.y
        elif self.popup_pos == POS_SE_NE:
            x -= (popup_alloc.width - btn_alloc.width)
            y = btn_window_xy.y - popup_alloc.height
        elif self.popup_pos == POS_SW_NW:
            y = btn_window_xy.y - popup_alloc.height
        elif self.popup_pos == POS_CENTER_BELOW:
            x -= (popup_alloc.width - btn_alloc.width) / 2
        elif self.popup_pos == POS_CENTER_ABOVE:
            x -= (popup_alloc.width - btn_alloc.width) / 2
            y = btn_window_xy.y - popup_alloc.height

        return x, y

    def hide_popup(self):
        self.set_active(False)

    def show_popup(self):
        self.set_active(True)

    def _do_hide_popup(self):
        if self._parent_button_press_id and self.get_toplevel().handler_is_connected(self._parent_button_press_id):
            self.get_toplevel().disconnect(self._parent_button_press_id)
            self._parent_button_press_id = None
        self.update_popup()
        self.emit('hidden')

    def _do_show_popup(self):
        if not self._parent_button_press_id and self.get_toplevel():
            self._parent_button_press_id = self.get_toplevel().connect('button-press-event', self._on_focus_out_event)
        self.update_popup()
        self.emit('shown')

    def update_popup(self):
        """Show the pop-up while the button is active and its widget is
            visible, otherwise hide it."""
        if self.get_active() and self.popup.get_child().get_visible() and self._main_window_focused:
            if self.popup.props.visible:
                self._update_popup_geometry()
            elif not self._show_tick_id:
                # Once the button stops moving (its row may still be scrolling
                # into place), so it shows once, in place.
                self._last_position = None
                self._ticks_left = MAX_SHOW_TICKS
                self._show_tick_id = self.add_tick_callback(self._on_show_tick)
        else:
            if self._show_tick_id:
                self.remove_tick_callback(self._show_tick_id)
                self._show_tick_id = None
            self.popup.hide()

    def _on_show_tick(self, _widget, _frame_clock):
        window = self.get_window()
        position = window and (window.get_origin()[1:], self.get_allocation().y)
        self._ticks_left -= 1
        if self._ticks_left > 0 and (not position or position != self._last_position):
            self._last_position = position
            return GLib.SOURCE_CONTINUE
        self._show_tick_id = None
        self._update_popup_geometry()
        self.popup.present()
        return GLib.SOURCE_REMOVE

    def _update_popup_geometry(self):
        # Until the button has a window there's nothing to place it by;
        # its next draw does.
        if self.get_window() is None:
            return
        # The content's own size: the pop-up's would include any size
        # request set below, and clearing that each time resizes it.
        requisition = self.popup.get_child().get_preferred_size()[1]
        width = requisition.width
        height = requisition.height
        request = (-1, -1)

        x, y = -1, -1
        popup_alloc = self.popup.get_allocation()
        btn_window_xy = self.get_window().get_origin()
        btn_alloc = self.get_allocation()

        if callable(self._update_popup_geometry_func):
            x, y, new_width, new_height = self._update_popup_geometry_func(
                self.popup, popup_alloc, btn_alloc, btn_window_xy,
                (x, y, width, height)
            )
            if new_width != width or new_height != height:
                width, height = new_width, new_height
                request = (width, height)
        if tuple(self.popup.get_size_request()) != request:
            self.popup.set_size_request(*request)

        self._placed_anchor = self._anchor()
        popup_alloc.width, popup_alloc.height = width, height
        x, y = self.calculate_popup_xy(popup_alloc, btn_alloc, btn_window_xy)
        self.popup.move(x, y)
        # The GtkWindow's own size too: on macOS it otherwise keeps laying its
        # content out at the old size, cutting off rows added since.
        if tuple(self.popup.get_size()) != (width, height):
            self.popup.resize(width, height)
        self.popup.get_window().get_toplevel().move_resize(x, y, width, height)


    # EVENT HANDLERS #
    def _on_focus_out_event(self, window, event):
        self.hide_popup()

    def _on_main_window_focus_changed(self, window, event, focused):
        self._main_window_focused = focused
        self.update_popup()
        return False

    def _on_key_press_event(self, window, event):
        if event.keyval == Gdk.KEY_Escape and self.popup.props.visible:
            self.hide_popup()
            return True
        return False

    def _on_popup_check_resize(self, popup):
        # The widget's size changed: place the pop-up again, after this layout.
        if popup.props.visible and not self._place_popup_id:
            self._place_popup_id = GLib.idle_add(self._place_popup)

    def _place_popup(self):
        self._place_popup_id = None
        self._update_popup_geometry()
        return False

    def _on_toggled(self, button):
        if button.get_active():
            self._do_show_popup()
        else:
            self._do_hide_popup()

    def _anchor(self):
        window = self.get_window()
        alloc = self.get_allocation()
        return window and (tuple(window.get_origin()[1:]), alloc.x, alloc.y, alloc.width, alloc.height)

    def _on_expose(self, widget, event):
        # Follow the button when it moves, not on every redraw: on macOS
        # moving the pop-up redraws the button again.
        if self.popup.props.visible and self._anchor() != self._placed_anchor:
            self._update_popup_geometry()


if __name__ == '__main__':
    btn = PopupWidgetButton(label='TestMe', widget=Gtk.Button('Click me'))

    hb = Gtk.HBox()
    hb.pack_start(Gtk.Button('Left', True, True, 0), expand=False, fill=False)
    hb.pack_start(btn,                 expand=False, fill=False)
    hb.pack_start(Gtk.Button('Right', True, True, 0), expand=False, fill=False)
    vb = Gtk.VBox()
    vb.pack_start(hb, expand=False, fill=False)

    from gtk import Window
    wnd = Window()
    wnd.set_size_request(400, 300)
    wnd.set_title('Pop-up Window Button Test')
    wnd.add(vb)
    wnd.connect('destroy', lambda *args: Gtk.main_quit())
    wnd.show_all()
    Gtk.main()
