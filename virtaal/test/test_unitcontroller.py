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

from gi.repository import GLib

from test_scaffolding import TestScaffolding

from virtaal.controllers.placeablescontroller import PlaceablesController


class TestUnitController(TestScaffolding):



    def test_get_target(self):
        # The unit indexes below differ by 1, because the StoreModel class (and thus the rest of Virtaal)
        # ignores PO headers (and other untranslatable units), whereas the Toolkit's stores do not.

        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)

        assert str(self.unit_controller.view.targets[0].elem) == self.trans_store.getunits()[1].target

    def test_set_target(self):
        test_unit = self.trans_store.getunits()[1]
        view = self.unit_controller.load_unit(test_unit)

        self.unit_controller.set_unit_target(0, [u'Test',])
        assert str(self.unit_controller.view.targets[0].elem) == u'Test'

    def test_stale_alt_down_does_not_corrupt_a_later_unit(self):
        """Alt+Down ('transfer from source') defers its copy via
        GLib.idle_add(). If the loaded unit changes before that runs,
        it must skip rather than overwrite the new unit with the old
        one's source text."""
        if not getattr(self.main_controller, 'placeables_controller', None):
            PlaceablesController(self.main_controller)

        units = self.trans_store.getunits()
        unit_a, unit_b = units[1], units[2]

        self.unit_controller.load_unit(unit_a)
        view = self.unit_controller.view
        textbox = view.targets[0]

        original_b_target = str(unit_b.target)

        # Intercept GLib.idle_add() rather than pumping the real main
        # loop - main-loop pumping has hung CI elsewhere in this
        # codebase. Invoking the captured callback directly tests the
        # real closure with no main-loop involvement at all.
        scheduled = []
        real_idle_add = GLib.idle_add
        GLib.idle_add = lambda callback, *a, **kw: scheduled.append(callback)
        try:
            # Real Alt+Down keypress on unit A.
            textbox.emit('key-pressed', None, 'alt-down')
        finally:
            GLib.idle_add = real_idle_add
        assert scheduled, 'Alt+Down should have scheduled a deferred copy'

        # Navigate to a different unit before that callback runs.
        self.unit_controller.load_unit(unit_b)
        self.store_controller.set_modified(False)

        scheduled[0]()  # run the now-stale callback

        assert str(unit_b.target) == original_b_target
        assert not self.store_controller.is_modified()
