#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
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

import logging
import os

from virtaal.controllers import *


class Virtaal(object):
    """The main Virtaal program entry point."""

    def __init__(self, startupfile):
        main_controller = MainController()
        logging.debug('MainController created')
        plugin_controller = PluginController(main_controller)
        main_controller.plugin_controller = plugin_controller
        logging.debug('PluginController created')
        store_controller = StoreController(main_controller)
        logging.debug('StoreController created')
        UnitController(store_controller)
        logging.debug('UnitController created')

        # Load additional built-in modules
        ChecksController(main_controller)
        logging.debug('ChecksController created')
        UndoController(main_controller)
        logging.debug('UndoController created')
        ModeController(main_controller)
        logging.debug('ModeController created')
        LanguageController(main_controller)
        logging.debug('LanguageController created')
        PlaceablesController(main_controller)
        logging.debug('PlaceablesController created')
        PreferencesController(main_controller)
        logging.debug('PreferencesController created')
        WelcomeScreenController(main_controller)
        logging.debug('WelcomeScreenController created')

        # Load plug-ins
        plugin_controller.load_plugins()
        logging.debug('Plugins loaded')

        # Load the file given on the command-line, if any
        if startupfile:
            main_controller.open_file(startupfile)
        else:
            store_controller.close_file() # Just to emit the "store-closed" event

        self.main_controller = main_controller


    # METHODS #
    def run(self):
        self.main_controller.run()
        self.main_controller.destroy()
        del self.main_controller


if __name__ == '__main__':
    check_toolkit_version()
    virtaal = Virtaal()
    virtaal.run()
