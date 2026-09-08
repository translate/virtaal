#!/usr/bin/env python
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


class TestStoreController(TestScaffolding):
    def test_open_file(self):
        self.store_controller.open_file(self.testfile[1])
        assert self.store_controller.store.get_filename() == self.testfile[1]

    def test_get_bundle_filename_on_a_plain_file(self):
        """Regression: get_bundle_filename() imported
        translate.storage.bundleprojstore unconditionally, before
        checking whether a project bundle was actually open - a module
        translate-toolkit no longer ships, so this crashed Save As
        (maincontroller.save_file() -> get_bundle_filename()) for every
        plain, non-bundle file, i.e. always."""
        self.store_controller.open_file(self.testfile[1])
        assert self.store_controller.get_bundle_filename() is None
