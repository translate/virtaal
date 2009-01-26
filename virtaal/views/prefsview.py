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
import gtk.gdk

from baseview import BaseView


class PreferencesView(BaseView):
    """Load, display and control the "Preferences" dialog."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self._init_gui()

    def _get_widgets(self):
        self.gladefile, self.gui = self.load_glade_file(
            ["virtaal", "virtaal.glade"],
            root='PreferencesDlg',
            domain="virtaal"
        )

        self._widgets = {}
        widget_names = ('tvw_plugins',)
        for name in widget_names:
            self._widgets[name] = self.gui.get_widget(name)

        self._widgets['dialog'] = self.gui.get_widget('PreferencesDlg')

    def _init_gui(self):
        self._get_widgets()
        self._setup_menu_item()
        self._setup_key_bindings()
        self._init_plugins_page()

    def _init_plugins_page(self):
        self.lst_plugins = gtk.ListStore(bool, str, str)
        tvw_plugins = self._widgets['tvw_plugins']
        tvw_plugins.set_model(self.lst_plugins)

        toggle_renderer = gtk.CellRendererToggle()
        toggle_renderer.connect('toggled', self._on_plugin_toggled)
        text_renderer = gtk.CellRendererText()

        tvc_enabled = gtk.TreeViewColumn(_('Enabled'), toggle_renderer, active=0)
        tvc_name = gtk.TreeViewColumn(_('Name'), text_renderer, text=1)

        tvw_plugins.append_column(tvc_enabled)
        tvw_plugins.append_column(tvc_name)

    def _setup_key_bindings(self):
        gtk.accel_map_add_entry("<Virtaal>/Edit/Preferences", gtk.keysyms.p, gtk.gdk.CONTROL_MASK)

        self.accel_group = gtk.AccelGroup()
        self.accel_group.connect_by_path("<Virtaal>/Edit/Preferences", self._show_preferences)

        mainview = self.controller.main_controller.view
        mainview.add_accel_group(self.accel_group)

    def _setup_menu_item(self):
        mainview = self.controller.main_controller.view
        mnu_prefs = mainview.gui.get_widget('mnu_prefs')
        mnu_prefs.connect('activate', self._show_preferences)

    # ACCESSORS #
    def _get_plugin_data(self):
        return tuple([ (row[0], row[1], row[2]) for row in self.lst_plugins ])
    def _set_plugin_data(self, value):
        tvw_plugins = self._widgets['tvw_plugins']
        model, selected_iter = tvw_plugins.get_selection().get_selected()

        if selected_iter is None or not self.lst_plugins.iter_is_valid(selected_iter):
            selected_name = ''
        else:
            selected_name = self.lst_plugins.get_value(selected_iter, 2)

        self.lst_plugins.clear()
        for enabled, name, int_name in value:
            self.lst_plugins.append([enabled, name, int_name])

        itr = self.lst_plugins.get_iter_first()
        while itr is not None and self.lst_plugins.iter_is_valid(itr):
            if self.lst_plugins.get_value(itr, 2) == selected_name:
                tvw_plugins.get_selection().select_iter(itr)
                break
            itr = self.lst_plugins.iter_next(itr)
    plugin_data = property(_get_plugin_data, _set_plugin_data)


    # METHODS #
    def show(self):
        self.controller.update_prefs_gui_data()
        response = self._widgets['dialog'].run()
        self._widgets['dialog'].hide()

        if response != gtk.RESPONSE_OK:
            return False
        return True


    # EVENT HANDLERS #
    def _on_plugin_toggled(self, cell, path):
        itr = self.lst_plugins.get_iter(path)
        enabled = not self.lst_plugins.get_value(itr, 0)
        internal_plugin_name = self.lst_plugins.get_value(itr, 2)

        self.controller.set_plugin_enabled(plugin_name=internal_plugin_name, enabled=enabled)
        self.lst_plugins.set_value(itr, 0, enabled)

    def _show_preferences(self, *args):
        self.show()
