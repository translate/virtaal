#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import GObjectWrapper
from .basecontroller import BaseController


class PropertiesController(BaseController):
    """Controller for driving the properties GUI."""

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
