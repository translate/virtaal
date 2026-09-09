#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from test_scaffolding import TestScaffolding


class TestMainController(TestScaffolding):
    def test_get_store(self):
        self.store_controller.open_file(self.testfile[1])
        assert self.main_controller.get_store() == self.store_controller.store
        assert self.main_controller.get_store_filename() == self.store_controller.store.get_filename()
