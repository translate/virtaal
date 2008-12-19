#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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

from baseview import BaseView
from widgets.storeviewwidgets import *


# XXX: ASSUMPTION: The model to display is self.controller.store
# TODO: Add event handler for store controller's cursor-creation event, so that
#       the store view can connect to the new cursor's "cursor-changed" event
#       (which is currently done in load_store())
class StoreView(BaseView):
    """The view of the store and interface to store-level actions."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        # XXX: While I can't think of a better way to do this, the following line would have to do :/
        self.parent_widget = self.controller.main_controller.view.gui.get_widget('scrolledwindow1')

        self._init_treeview()
        self.load_store(self.controller.store)

        self.controller.main_controller.view.main_window.connect('configure-event', self._treeview.on_configure_event)

    def _init_treeview(self):
        self._treeview = StoreTreeView(self)


    # ACCESSORS #
    def _get_cursor(self):
        return self.controller.cursor
    cursor = property(_get_cursor)

    def get_store(self):
        return self.store

    def get_unit_celleditor(self, unit):
        return self.controller.get_unit_celleditor(unit)


    # METHODS #
    def load_store(self, store):
        self.store = store
        if store:
            self._treeview.set_model(store)
            self.cursor.connect('cursor-changed', self._on_cursor_change)

    def show(self):
        child = self.parent_widget.get_child()
        if child is not self._treeview:
            self.parent_widget.remove(child)
            child.destroy()
            self.parent_widget.add(self._treeview)
        self._treeview.show()
        self._treeview.select_index(0)

        if self._treeview.get_model():
            selection = self._treeview.get_selection()
            selection.select_iter(self._treeview.get_model().get_iter_first())


    # EVENT HANDLERS #
    def _on_cursor_change(self, cursor):
        self._treeview.select_index(cursor.index)
