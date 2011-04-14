#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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


# This is the main loader for Virtaal. We want the GUI to show really quickly,
# so do a few unusual things. The _Deferer helps us to serialise events in idle
# spots in the gobject event loop, so that we can load some expensive stuff
# after the GUI is already showing.


import gobject


class _Deferer:
    _todo = []

    def __call__(self, func, *args):
        def next_job():
            # We return True if we want gobject to schedule this again while
            # there is still something to do
            try:
                (func, args) = self._todo.pop(0)
            except IndexError:
                # This is possible if a previous func() was last, but added
                # something during execution. Therefore a different next_job()
                # is in the event loop to handle that job, and will be gone
                # when we get round to doing this one again.
                return False
            func(*args)
            return bool(self._todo)

        if not self._todo:
            # No existing jobs, so start one
            gobject.idle_add(next_job)
        self._todo.append((func, args))


class Virtaal(object):
    """The main Virtaal program entry point."""

    def __init__(self, startupfile):
        # We try to get the welcomescreen loaded as early as possible
        from virtaal.controllers.maincontroller import MainController
        from virtaal.controllers.welcomescreencontroller import WelcomeScreenController
        from virtaal.controllers.storecontroller import StoreController

        main_controller = MainController()
        store_controller = StoreController(main_controller)

        self.defer = _Deferer()
        self.main_controller = main_controller

        if startupfile:
            # Just call the open plainly - we want it done before we start the
            # event loop.
            if self._open_with_file(startupfile):
                self.defer(WelcomeScreenController, main_controller)
            else:
                # Something went wrong, and we have to show the welcome screen
                wc = WelcomeScreenController(main_controller)
                wc.activate()

        else:
            wc = WelcomeScreenController(main_controller)
            wc.activate()
            # Now we try to get the event loop started as quickly as possible,
            # so we defer as much as possible.
            self.defer(self._open_with_welcome)
        self.defer(self._load_extras)


    def _open_with_file(self, startupfile):
        # Things needed for opening a file, including inter-dependencies
        from virtaal.controllers.unitcontroller import UnitController
        from virtaal.controllers.modecontroller import ModeController
        from virtaal.controllers.langcontroller import LanguageController
        from virtaal.controllers.placeablescontroller import PlaceablesController

        main_controller = self.main_controller

        if isinstance(startupfile, str):
            import sys
            startupfile = unicode(startupfile, sys.getfilesystemencoding())

        UnitController(main_controller.store_controller)
        ModeController(main_controller)
        LanguageController(main_controller)
        PlaceablesController(main_controller)

        return main_controller.open_file(startupfile)

    def _open_with_welcome(self):
        from virtaal.controllers.unitcontroller import UnitController
        from virtaal.controllers.modecontroller import ModeController
        from virtaal.controllers.langcontroller import LanguageController
        from virtaal.controllers.placeablescontroller import PlaceablesController

        defer = self.defer
        main_controller = self.main_controller

        defer(UnitController, self.main_controller.store_controller)
        defer(ModeController, main_controller)
        defer(LanguageController, main_controller)
        defer(PlaceablesController, main_controller)

    def _load_extras(self):
        from virtaal.controllers.plugincontroller import PluginController
        from virtaal.controllers.prefscontroller import PreferencesController
        from virtaal.controllers.checkscontroller import ChecksController
        from virtaal.controllers.undocontroller import UndoController
        from virtaal.controllers.propertiescontroller import PropertiesController

        defer = self.defer
        main_controller = self.main_controller

        defer(ChecksController, main_controller)
        defer(UndoController, main_controller)
        defer(PluginController, main_controller)
        defer(PreferencesController, main_controller)
        defer(PropertiesController, main_controller)
        defer(main_controller.load_plugins)


    # METHODS #
    def run(self):
        self.main_controller.run()
        self.main_controller.destroy()
        del self.main_controller


if __name__ == '__main__':
    virtaal = Virtaal()
    virtaal.run()
