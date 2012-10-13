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

from test_scaffolding import TestScaffolding


class TestUnitController(TestScaffolding):



    def test_get_target(self):
        # The unit indexes below differ by 1, because the StoreModel class (and thus the rest of Virtaal)
        # ignores PO headers (and other untranslatable units), whereas the Toolkit's stores do not.
        assert self.unit_controller.get_unit_target(0) == self.trans_store.getunits()[1].target

    def test_set_target(self):
        self.unit_controller.set_unit_target(0, 'Test')
        assert self.unit_controller.get_unit_target(0) == 'Test'
