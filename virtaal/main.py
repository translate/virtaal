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

import os

from virtaal.controllers import *


class Virtaal(object):
    """The main Virtaal program entry point."""

    def __init__(self, startupfile):
        self.main_controller = MainController()
        self.plugin_controller = PluginController(self.main_controller)
        self.main_controller.plugin_controller = self.plugin_controller
        self.store_controller = StoreController(self.main_controller)
        self.unit_controller = UnitController(self.store_controller)

        # Load additional built-in modules
        self.undo_controller = UndoController(self.main_controller)
        self.mode_controller = ModeController(self.main_controller)

        # Load plug-ins
        self.plugin_controller.load_plugins()

        # Load the file given on the command-line, if any
        if startupfile and os.path.isfile(startupfile):
            self.main_controller.open_file(startupfile)


    # METHODS #
    def run(self):
        self.main_controller.run()


if __name__ == '__main__':
    virtaal = Virtaal()
    virtaal.run()
