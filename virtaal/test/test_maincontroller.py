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

    def test_revert_file_discards_an_unsaved_edit(self, monkeypatch):
        with open(self.testfile[1], 'rb') as f:
            on_disk = f.read()
        self.store_controller.open_file(self.testfile[1])
        unit = self.store_controller.store.get_units()[0]
        original = unit.target
        unit.target = 'Edited, not saved'
        self.unit_controller.emit('unit-modified', unit)
        assert self.store_controller.is_modified()
        monkeypatch.setattr(self.main_controller, 'show_prompt', lambda *a, **kw: True)

        self.main_controller.revert_file()

        assert self.store_controller.store.get_units()[0].target == original
        assert not self.store_controller.is_modified()
        with open(self.testfile[1], 'rb') as f:
            assert f.read() == on_disk
