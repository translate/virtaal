#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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
        unit_controller = UnitController(store_controller)
        logging.debug('UnitController created')

        # Load additional built-in modules
        undo_controller = UndoController(main_controller)
        logging.debug('UndoController created')
        mode_controller = ModeController(main_controller)
        logging.debug('ModeController created')
        lang_controller = LanguageController(main_controller)
        logging.debug('LanguageController created')
        placeables_controller = PlaceablesController(main_controller)
        logging.debug('PlaceablesController created')
        prefs_controller = PreferencesController(main_controller)
        logging.debug('PreferencesController created')

        # Load plug-ins
        plugin_controller.load_plugins()
        logging.debug('Plugins loaded')

        # Load the file given on the command-line, if any
        if startupfile:
            main_controller.open_file(startupfile)

        self.main_controller = main_controller


    # METHODS #
    def run(self):
        self.main_controller.run()


def checkversions():
    """Checks that version dependencies are met"""
    from translate import __version__ as toolkitversion
    if not hasattr(toolkitversion, "ver") or toolkitversion.ver < (1, 2, 1):
        raise RuntimeError("requires Translate Toolkit version >= 1.2.1.  Current installed version is: %s" % toolkitversion.sver)

if __name__ == '__main__':
    check_toolkit_version()
    virtaal = Virtaal()
    virtaal.run()
