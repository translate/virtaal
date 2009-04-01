#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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
import gtk.glade
from gobject import SIGNAL_RUN_FIRST, TYPE_PYOBJECT

from virtaal.common import GObjectWrapper

__all__ = ['COL_ENABLED', 'COL_NAME', 'COL_DESC', 'COL_DATA', 'SelectView']

COL_ENABLED, COL_NAME, COL_DESC, COL_DATA = range(4)


class SelectView(gtk.TreeView, GObjectWrapper):
    """
    A tree view that enables the user to select items from a list.
    """

    __gtype_name__ = 'SelectView'
    __gsignals__ = {
        'item-enabled':  (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'item-disabled': (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'item-selected': (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
    }

    CONTENT_VBOX = 'vb_content'
    """The name of the C{gtk.VBox} containing the selection items."""

    # INITIALIZERS #
    def __init__(self, items=None, bold_name=True):
        gtk.TreeView.__init__(self)
        GObjectWrapper.__init__(self)

        if not items:
            items = gtk.ListStore(bool, str, str, TYPE_PYOBJECT)
        self.set_model(items)
        self.bold_name = bold_name

        self._add_columns()
        self._set_defaults()
        self._connect_events()

    def _add_columns(self):
        cell = gtk.CellRendererToggle()
        cell.connect('toggled', self._on_item_toggled)
        self.select_col = gtk.TreeViewColumn(_('Enabled'), cell, active=COL_ENABLED)
        self.append_column(self.select_col)

        cell = gtk.CellRendererText()
        self.namedesc_col = gtk.TreeViewColumn(_('Name'), cell)
        self.namedesc_col.set_cell_data_func(cell, self._name_cell_data_func)
        self.append_column(self.namedesc_col)

    def _connect_events(self):
        self.get_selection().connect('changed', self._on_selection_change)

    def _set_defaults(self):
        self.set_rules_hint(True)


    # METHODS #
    def get_all_items(self):
        if not self._model:
            return None
        return [
            {
                'enabled': row[COL_ENABLED],
                'name':    row[COL_NAME],
                'desc':    row[COL_DESC],
                'data':    row[COL_DATA]
            } for row in self._model
        ]

    def get_item(self, iter):
        if not self._model:
            return None
        if not self._model.iter_is_valid(iter):
            return None

        return {
            'enabled': self._model.get_value(iter, COL_ENABLED),
            'name':    self._model.get_value(iter, COL_NAME),
            'desc':    self._model.get_value(iter, COL_DESC),
            'data':    self._model.get_value(iter, COL_DATA),
        }

    def set_model(self, items):
        if isinstance(items, gtk.ListStore):
            self._model = items
        else:
            self._model = gtk.ListStore(bool, str, str, TYPE_PYOBJECT)
            for row in items:
                self._model.append([
                    row.get('enabled', False),
                    row.get('name', ''),
                    row.get('desc', ''),
                    row.get('data', None)
                ])

        gtk.TreeView.set_model(self, self._model)


    # EVENT HANDLERS #
    def _name_cell_data_func(self, column, cell_renderer, tree_model, iter):
        name = tree_model.get_value(iter, COL_NAME)
        desc = tree_model.get_value(iter, COL_DESC)
        if self.bold_name:
            cell_renderer.props.markup = "<b>%s</b>\n%s" % (name, desc)
        elif name:
            cell_renderer.props.text = '%s\n%s' % (name, desc)
        else:
            cell_renderer.props.text = desc

    def _on_item_toggled(self, cellr, path):
        iter = self._model.get_iter(path)
        if not iter:
            return
        item_info = self.get_item(iter)
        item_info['enabled'] = not item_info['enabled']
        self._model.set_value(iter, COL_ENABLED, item_info['enabled'])

        if item_info['enabled']:
            self.emit('item-enabled', item_info)
        else:
            self.emit('item-disabled', item_info)

    def _on_selection_change(self, selection):
        model, iter = selection.get_selected()
        if None is not model is self._model and self._model.iter_is_valid(iter):
            self.emit('item-selected', self.get_item(iter))
