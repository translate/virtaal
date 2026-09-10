#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from test_scaffolding import TestScaffolding

from virtaal.models.storemodel import StoreModel


class TestStoreModel(TestScaffolding):
    def test_load(self):
        self.model = StoreModel(self.testfile[1], None) # We can pass "None" as the controller, because it does not have an effect on this test
        self.model.load_file(self.testfile[1])
        assert len(self.model) <= len(self.trans_store.units)
        assert self.model.get_filename() == self.testfile[1]


def test_compute_nplurals_infers_from_data_when_the_format_has_no_declaration():
    # .qm has no working plural-count declaration to read (translate-
    # toolkit's own NumerusRules section reader is unimplemented) -
    # translate/virtaal#1501.
    from translate.storage import factory
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    assert StoreModel._compute_nplurals(None, store) == 2


def test_compute_nplurals_none_without_any_plural_data():
    from translate.storage import mo
    store = mo.mofile()
    assert StoreModel._compute_nplurals(None, store) is None
