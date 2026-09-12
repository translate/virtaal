#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject, Gtk
from gi.repository.GObject import TYPE_PYOBJECT

from virtaal.common import GObjectWrapper

from .selectview import SelectView


class SelectDialog(GObjectWrapper):
    """
    A dialog wrapper to easily select items from a list.
    """

    __gtype_name__ = 'SelectDialog'
    __gsignals__ = {
        'item-enabled':   (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'item-disabled':  (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'item-selected':  (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'selection-done': (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
    }

    # INITIALIZERS #
    def __init__(self, items=None, title=None, message=None, parent=None, size=None):
        super().__init__()
        self.sview = SelectView(items)
        self._create_gui(title, message, parent)
        self._connect_signals()

        if size and len(size) == 2:
            w, h = -1, -1
            if size[0] > 0:
                w = size[0]
            if size[1] > 0:
                h = size[1]
            self.dialog.set_size_request(w, h)

    def _connect_signals(self):
        self.sview.connect('item-enabled',  self._on_item_enabled)
        self.sview.connect('item-disabled', self._on_item_disabled)
        self.sview.connect('item-selected', self._on_item_selected)

    def _create_gui(self, title, message, parent):
        self.dialog = Gtk.Dialog()
        self.dialog.set_modal(True)
        if isinstance(parent, Gtk.Widget):
            self.set_transient_for(parent)
        self.dialog.set_title(title is not None and title or 'Select items')
        self.message = Gtk.Label(label=message is not None and message or '')
        self.dialog.get_child().pack_start(self.message, expand=False, fill=False, padding=10)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        # A ScrolledWindow doesn't request its child's actual width by
        # default - it happily shrinks it and adds a horizontal
        # scrollbar instead, which is how a row's inline "Configure..."
        # button ended up clipped. Grow to fit instead, so this scales
        # with whatever a given translation's actual text needs rather
        # than a fixed guess in one language.
        scrolled_window.set_propagate_natural_width(True)
        scrolled_window.add(self.sview)
        self.dialog.get_child().pack_end(scrolled_window, True, True, 0)
        self.dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)


    # METHODS #
    def get_message(self):
        return self.message.get_text()

    def set_icon(self, icon):
        """Simple proxy method to C{self.dialog.set_icon(icon)}."""
        self.dialog.set_icon(icon)

    def set_message(self, msg):
        self.message.set_text(msg)

    def set_transient_for(self, parent):
        """Simple proxy method to C{self.dialog.set_transient_for(parent)}."""
        self.dialog.set_transient_for(parent)

    def run(self, items=None, parent=None):
        if items is not None:
            self.sview.set_model(items)
        if isinstance(parent, Gtk.Widget):
            self.dialog.reparent(parent)
        self.dialog.show_all()
        self.response = self.dialog.run()
        self.dialog.hide()
        self.emit('selection-done', self.sview.get_all_items())
        return self.response


    # EVENT HANDLERS #
    def _on_item_enabled(self, selectview, item):
        self.emit('item-enabled', item)

    def _on_item_disabled(self, selectview, item):
        self.emit('item-disabled', item)

    def _on_item_selected(self, selectview, item):
        self.emit('item-selected', item)
