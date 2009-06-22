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

from virtaal.views.widgets.selectview import SelectView

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
        widget_names = ('scrwnd_placeables', 'scrwnd_plugins',)
        for name in widget_names:
            self._widgets[name] = self.gui.get_widget(name)

        self._widgets['dialog'] = self.gui.get_widget('PreferencesDlg')
        self._widgets['dialog'].set_transient_for(self.controller.main_controller.view.main_window)

    def _init_gui(self):
        self._get_widgets()
        self._setup_menu_item()
        self._setup_key_bindings()
        self._init_placeables_page()
        self._init_plugins_page()

    def _init_placeables_page(self):
        self.placeables_select = SelectView()
        self.placeables_select.connect('item-enabled', self._on_placeable_toggled)
        self.placeables_select.connect('item-disabled', self._on_placeable_toggled)
        self._widgets['scrwnd_placeables'].add(self.placeables_select)
        self._widgets['scrwnd_placeables'].show_all()

    def _init_plugins_page(self):
        self.plugins_select = SelectView()
        self.plugins_select.connect('item-enabled', self._on_plugin_toggled)
        self.plugins_select.connect('item-disabled', self._on_plugin_toggled)
        self._widgets['scrwnd_plugins'].add(self.plugins_select)
        self._widgets['scrwnd_plugins'].show_all()

    def _setup_key_bindings(self):
        gtk.accel_map_add_entry("<Virtaal>/Edit/Preferences", gtk.keysyms.p, gtk.gdk.CONTROL_MASK)

        self.accel_group = gtk.AccelGroup()
        self.accel_group.connect_by_path("<Virtaal>/Edit/Preferences", self._show_preferences)

        mainview = self.controller.main_controller.view
        mainview.add_accel_group(self.accel_group)

    def _setup_menu_item(self):
        mainview = self.controller.main_controller.view
        mnu_prefs = mainview.gui.get_widget('mnu_prefs')
        mnu_prefs.set_accel_path("<Virtaal>/Edit/Preferences")
        mnu_prefs.connect('activate', self._show_preferences)

    # ACCESSORS #
    def _get_placeables_data(self):
        return self.placeables_select.get_all_items()
    def _set_placeables_data(self, value):
        selected = self.placeables_select.get_selected_item()
        self.placeables_select.set_model(value)
        self.placeables_select.select_item(selected)
    placeables_data = property(_get_placeables_data, _set_placeables_data)

    def _get_plugin_data(self):
        return self.plugins_select.get_all_items()
    def _set_plugin_data(self, value):
        selected = self.plugins_select.get_selected_item()
        self.plugins_select.set_model(value)
        self.plugins_select.select_item(selected)
    plugin_data = property(_get_plugin_data, _set_plugin_data)


    # METHODS #
    def show(self):
        self.placeables_select.select_item(None)
        self.plugins_select.select_item(None)
        self.controller.update_prefs_gui_data()
        #logging.debug('Plug-in data: %s' % (str(self.plugin_data)))
        self._widgets['dialog'].run()
        self._widgets['dialog'].hide()


    # EVENT HANDLERS #
    def _on_placeable_toggled(self, sview, item):
        self.controller.set_placeable_enabled(
            parser=item['data'],
            enabled=item['enabled']
        )

    def _on_plugin_toggled(self, sview, item):
        self.controller.set_plugin_enabled(
            plugin_name=item['data']['internal_name'],
            enabled=item['enabled']
        )

    def _show_preferences(self, *args):
        self.show()
