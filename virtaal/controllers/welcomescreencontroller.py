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
from virtaal.support import openmailto
from virtaal.views.welcomescreenview import WelcomeScreenView

from basecontroller import BaseController


class WelcomeScreenController(BaseController):
    """
    Contains logic for the welcome screen.
    """

    LINKS = {
        'manual':   'http://translate.sourceforge.net/wiki/virtaal/using_virtaal',
        'locguide': 'http://translate.sourceforge.net/wiki/guide/start',
        # FIXME: The URL below should be replaced with a proper feedback URL
        'feedback': 'http://bugs.locamotion.org/enter_bug.cgi?product=Virtaal',
    }

    # INITIALIZERS #
    def __init__(self, main_controller):
        self.main_controller = main_controller
        main_controller.welcomescreen_controller = self

        self._recent_files = []
        self.view = WelcomeScreenView(self)

        main_controller.store_controller.connect('store-closed', self._on_store_closed)
        main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        self.view.show()


    # METHODS #
    def activate(self):
        """Show the welcome screen and trigger activation logic (ie. find
            recent files)."""
        self.view.show()

    def open_cheatsheat(self):
        # FIXME: The URL below is just a temporary solution
        openmailto.open('http://translate.sourceforge.net/wiki/virtaal/tips')

    def open_file(self):
        self.main_controller.open_file()

    def open_recent(self, n):
        if 0 <= n <= len(self._recent_files):
            self.main_controller.open_file(self._recent_files[n])
        else:
            logging.debug('Invalid recent file index (%d) given. Recent files: %s)' % (n, self._recent_files))

    def open_tutorial(self):
        self.main_controller.open_tutorial()

    def try_open_link(self, name):
        if name not in self.LINKS:
            return False
        openmailto.open(self.LINKS[name])
        return True


    # EVENT HANDLERS #
    def _on_store_closed(self, store_controller):
        self.view.show()

    def _on_store_loaded(self, store_controller):
        self.view.hide()
