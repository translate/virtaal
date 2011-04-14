#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Zuza Software Foundation
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


from virtaal.common import GObjectWrapper

from basecontroller import BaseController


class PropertiesController(BaseController):
    """Controller for driving the preferences GUI."""

    __gtype_name__ = 'PropertiesController'

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        from virtaal.views.propertiesview import PropertiesView
        self.view = PropertiesView(self)


    # METHODS #

    def update_gui_data(self):
        import os.path
        filename = os.path.abspath(self.main_controller.store_controller.get_store().get_filename())
        if os.path.exists(filename):
            self.view.data['file_location'] = filename
            self.view.data['file_size'] = os.path.getsize(filename)
        self.view.data['file_type'] = self.main_controller.store_controller.get_store().get_store_type()
        self.view.stats = self.main_controller.store_controller.get_store().get_stats_totals()

    # EVENT HANDLERS #
