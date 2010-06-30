#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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
from gobject import SIGNAL_RUN_FIRST
from translate.filters import checks

from virtaal.common import GObjectWrapper
from virtaal.views.checksview import ChecksView

from basecontroller import BaseController


class ChecksController(BaseController):
    """Controller for quality checks."""

    __gtype_name__ = 'ChecksController'
    __gsignals__ = {
        'unit-checked': (SIGNAL_RUN_FIRST, None, (object, object, object))
    }

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.checks_controller = self
        self.checks = checks

        main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        # XXX: Add other checkers below with a localisable string as key (used
        #      on the GUI) and a checker class as the value.
        self.checker_info = {
            _('Default'):    checks.StandardChecker,
            _('OpenOffice'): checks.OpenOfficeChecker,
            _('Mozilla'):    checks.MozillaChecker,
            _('Drupal'):     checks.DrupalChecker,
            _('GNOME'):      checks.GnomeChecker,
            _('KDE'):        checks.KdeChecker,
        }
        self._checker_menu_items = {}
        self._current_checker = None
        self._cursor_connection = ()

        self.view = ChecksView(self)
        self.view.show()


    # ACCESSORS #
    def get_current_checker(self):
        return self._current_checker

    def set_default_project_type(self):
        self.set_project_type_by_name(_('Default'))

    def set_project_type_by_name(self, name):
        checker = self.checker_info[name]()
        self._current_checker = checker
        self.view.set_checker_name(name)
        if self.main_controller.unit_controller.current_unit:
            self.check_unit(self.main_controller.unit_controller.current_unit)


    # METHODS #
    def check_unit(self, unit):
        checker = self.get_current_checker()
        if not checker:
            logging.debug('No checker instantiated :(')
            return
        self.last_failures = checker.run_filters(unit)
        if self.last_failures:
            logging.debug('Failures: %s' % (self.last_failures))
        self.emit('unit-checked', unit, checker, self.last_failures)


    # EVENT HANDLERS #
    def _on_cursor_changed(self, cursor):
        self.last_unit = cursor.deref()
        self.check_unit(self.last_unit)

    def _on_store_loaded(self, store_controller):
        self.set_default_project_type()
        if self._cursor_connection:
            widget, connect_id = self._cursor_connection
            widget.disconnect(connect_id)
        self._cursor_connection = (
            store_controller.cursor,
            store_controller.cursor.connect('cursor-changed', self._on_cursor_changed)
        )
        self._on_cursor_changed(store_controller.cursor)
