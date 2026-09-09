#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
