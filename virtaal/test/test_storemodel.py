#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.models.storemodel import StoreModel

from test_scaffolding import TestScaffolding


class TestStoreModel(TestScaffolding):
    def test_load(self):
        self.model = StoreModel(self.testfile[1], None) # We can pass "None" as the controller, because it does not have an effect on this test
        self.model.load_file(self.testfile[1])
        assert len(self.model) <= len(self.trans_store.units)
        assert self.model.get_filename() == self.testfile[1]
