#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gdk, Gtk, Pango

from virtaal.views import rendering


def popup_position(anchor, size, bounds, rtl=False):
    """Screen position for a popup of C{size} (width, height) next to the
    C{anchor} rectangle (x, y, width, height) - below it by default, above
    it when below doesn't fit - kept inside C{bounds} (x, y, width, height)
    when given."""
    ax, ay, _aw, ah = anchor
    width, height = size
    x = ax - width if rtl else ax
    y = ay + ah
    if bounds is None:
        return x, y

    bx, by, bw, bh = bounds
    if y + height > by + bh and ay - height >= by:
        y = ay - height
    x = max(bx, min(x, bx + bw - width))
    return x, y


class CompletionPopup(Gtk.Window):
    """
    A list of candidate strings shown at a text view's cursor.

    It is a popup window, so it never takes keyboard focus: the text view
    keeps it and forwards navigation keys with L{move_selection},
    L{accept} and L{dismiss}.
    """

    MAX_VISIBLE_ROWS = 8

    # INITIALIZERS #
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_type_hint(Gdk.WindowTypeHint.COMBO)
        self.set_destroy_with_parent(True)
        self._on_accept = None
        self._textview = None
        self._configure_id = None

        self._candidates = []
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.set_can_focus(False)
        self.listbox.connect('row-activated', self._on_row_activated)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled_window.add(self.listbox)
        self.add(self.scrolled_window)


    # METHODS #
    def is_showing(self):
        return self._on_accept is not None

    def show_at(self, textview, offset, candidates, on_accept):
        """Show C{candidates} below the character at C{offset} in
        C{textview}; C{on_accept} is called with the chosen string."""
        self.dismiss()
        if not candidates:
            return

        font = rendering.get_role_font_description(getattr(textview, 'role', None))
        self._fill(candidates, font or rendering.get_target_font_description())
        self.select_index(0)

        self._on_accept = on_accept
        self._textview = textview
        toplevel = textview.get_toplevel()
        if isinstance(toplevel, Gtk.Window):
            self.set_transient_for(toplevel)
            self.set_attached_to(textview)
            # Dismiss rather than chase the main window while it moves (#3924).
            self._configure_id = toplevel.connect('configure-event', self._on_configure_toplevel)

        self.scrolled_window.show_all()
        self._update_geometry(textview, offset)
        self.show()

    def select_index(self, index):
        if not self._candidates:
            return
        index = max(0, min(index, len(self._candidates) - 1))
        row = self.listbox.get_row_at_index(index)
        self.listbox.select_row(row)
        alloc = row.get_allocation()
        if alloc.height > 1:
            self.scrolled_window.get_vadjustment().clamp_page(alloc.y, alloc.y + alloc.height)

    def selected_index(self):
        row = self.listbox.get_selected_row()
        return None if row is None else row.get_index()

    def move_selection(self, delta):
        index = self.selected_index()
        self.select_index(delta if index is None else index + delta)

    def accept(self):
        """Dismiss and pass the selected candidate to the accept callback."""
        index = self.selected_index()
        on_accept = self._on_accept
        self.dismiss()
        if on_accept is not None and index is not None:
            on_accept(self._candidates[index])

    def dismiss(self):
        if self._configure_id is not None:
            self._textview.get_toplevel().disconnect(self._configure_id)
            self._configure_id = None
        self._on_accept = None
        self._textview = None
        self.hide()
        # On macOS a hidden transient window can be re-shown with its parent
        # (e.g. after dragging the main window); dropping the native window
        # rules that out.
        if self.get_realized():
            self.unrealize()

    def _fill(self, candidates, font):
        for row in self.listbox.get_children():
            row.destroy()
        self._candidates = list(candidates)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_font_desc_new(font))
        for candidate in self._candidates:
            label = Gtk.Label(label=candidate, xalign=0)
            label.set_attributes(attrs)
            label.set_margin_start(4)
            label.set_margin_end(4)
            row = Gtk.ListBoxRow()
            row.set_can_focus(False)
            row.add(label)
            row.show_all()
            self.listbox.add(row)

    def _update_geometry(self, textview, offset):
        gdkwin = textview.get_window(Gtk.TextWindowType.WIDGET)
        if gdkwin is None:
            return
        rect = textview.get_iter_location(textview.get_buffer().get_iter_at_offset(offset))
        wx, wy = textview.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, rect.x, rect.y)
        origin = gdkwin.get_origin()
        anchor = (origin.x + wx, origin.y + wy, rect.width, rect.height)

        _minimum, natural = self.listbox.get_preferred_size()
        row_height = natural.height // max(len(self._candidates), 1)
        # A vertical scrollbar's minimum length leaves blank space under a
        # short list, so only scroll when needed.
        if len(self._candidates) > self.MAX_VISIBLE_ROWS:
            visible_height = row_height * self.MAX_VISIBLE_ROWS
            self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self.scrolled_window.set_size_request(-1, visible_height)
        else:
            visible_height = natural.height
            self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
            self.scrolled_window.set_size_request(-1, -1)
        border = self.scrolled_window.get_style_context().get_border(Gtk.StateFlags.NORMAL)
        width = natural.width + border.left + border.right
        height = visible_height + border.top + border.bottom
        # Shrink from a previous, longer list.
        self.resize(width, height)

        bounds = None
        toplevel_window = textview.get_toplevel().get_window()
        if toplevel_window is not None:
            frame = toplevel_window.get_frame_extents()
            bounds = (frame.x, frame.y, frame.width, frame.height)

        rtl = textview.get_direction() == Gtk.TextDirection.RTL
        x, y = popup_position(anchor, (width, height), bounds, rtl)
        self.move(x, y)


    # EVENT HANDLERS #
    def _on_configure_toplevel(self, toplevel, event):
        self.dismiss()
        return False

    def _on_row_activated(self, listbox, row):
        self.select_index(row.get_index())
        self.accept()
