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

from virtaal.common import GObjectWrapper, pan_app
from virtaal.views import PreferencesView

from basecontroller import BaseController


class PreferencesController(BaseController):
    """Controller for driving the preferences GUI."""

    __gtype_name__ = 'PreferencesController'

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.plugin_controller = main_controller.plugin_controller
        self.view = PreferencesView(self)


    # METHODS #
    def set_plugin_enabled(self, plugin_name, enabled):
        """Enabled or disable a plug-in with the given name."""
        if enabled:
            self.plugin_controller.enable_plugin(plugin_name)
        else:
            self.plugin_controller.disable_plugin(plugin_name)

    def update_prefs_gui_data(self):
        plugin_data = []
        disabled = self.plugin_controller.get_disabled_plugins()
        for found_plugin in self.plugin_controller._find_plugin_names():
            if found_plugin in disabled:
                plugin_data.append((False, found_plugin, found_plugin))
            elif found_plugin in self.plugin_controller.plugins:
                plugin = self.plugin_controller.plugins[found_plugin]
                plugin_data.append((True, plugin.display_name, found_plugin))

        self.view.plugin_data = plugin_data
