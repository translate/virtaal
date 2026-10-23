#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Opening and saving through the real store and unit controllers, on
real files."""

import zipfile

import pytest
from test_scaffolding import TestScaffolding
from translate.storage import factory, workflow

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.support.bundleprojstore import BundleProjectStore, InvalidBundleError

PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Open"
msgstr ""
'''

XLIFF = b'''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="t" source-language="en" target-language="af" datatype="plaintext"><body>
<trans-unit id="1"><source>Open</source><target state="needs-translation">Oop</target></trans-unit>
<trans-unit id="2"><source>Close</source><target state="translated">Maak toe</target></trans-unit>
</body></file></xliff>
'''

CSV = b'source,target\nOpen,Oop\n'


def _zip_without_a_project(path):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('open.po', PO)
    return str(path)


def _bundle(tmp_path):
    po = tmp_path / 'open.po'
    po.write_bytes(PO)
    bundle = BundleProjectStore(str(tmp_path / 'project.zip'))
    bundle.append_file(str(po), None, 'trans')
    bundle.save()
    bundle.close()
    return str(tmp_path / 'project.zip')


def _target_state(path, source):
    unit = next(u for u in factory.getobject(path).units if u.source == source)
    return unit.get_state_n()


class TestStoreOpenSave(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        # The app always has one: without it a textbox never shows its text.
        PlaceablesController(self.main_controller)

    @pytest.fixture(autouse=True)
    def _closed(self, monkeypatch):
        # Saving a PO file asks for these in a modal dialog.
        monkeypatch.setattr(self.main_controller, 'get_translator_details',
                            lambda *args: ('Tester', 'tester@example.org', 'Afrikaans'))
        self.store_controller.close_file()
        yield
        self.store_controller.close_file()

    def test_a_zip_that_isnt_a_bundle_fails_with_its_reason(self, tmp_path):
        with pytest.raises(InvalidBundleError, match='Not a translate project bundle'):
            self.store_controller.open_file(_zip_without_a_project(tmp_path / 'other.zip'))

        assert self.store_controller.project is None
        assert self.store_controller.store is None

    def test_a_zip_that_isnt_a_bundle_leaves_the_open_bundle_open(self, tmp_path):
        bundle = _bundle(tmp_path)
        self.store_controller.open_file(bundle)

        with pytest.raises(InvalidBundleError):
            self.store_controller.open_file(_zip_without_a_project(tmp_path / 'other.zip'))

        assert self.store_controller.get_bundle_filename() == bundle

    def test_saving_a_bundle_file_it_doesnt_hold_fails(self, tmp_path):
        self.store_controller.open_file(_bundle(tmp_path))
        self.unit_controller.load_unit(self.store_controller.store.get_units()[0])
        self.store_controller.real_filename = str(tmp_path / 'elsewhere.po')

        with pytest.raises(ValueError, match='Real file not in project store'):
            self.store_controller.save_file()

    def test_saving_writes_a_state_chosen_in_the_unit(self, tmp_path):
        path = tmp_path / 'open.xlf'
        path.write_bytes(XLIFF)
        self.store_controller.open_file(str(path))
        unit = self.store_controller.store.get_units()[0]
        self.unit_controller.load_unit(unit)
        self.unit_controller.set_current_state(workflow.StateEnum.FINAL, from_user=True)
        unit._modified = True

        self.store_controller.save_file()

        assert _target_state(str(path), 'Open') == workflow.StateEnum.FINAL
        assert _target_state(str(path), 'Close') == workflow.StateEnum.UNREVIEWED

    def test_saving_an_unmodified_unit_keeps_its_state(self, tmp_path):
        path = tmp_path / 'open.xlf'
        path.write_bytes(XLIFF)
        self.store_controller.open_file(str(path))
        unit = self.store_controller.store.get_units()[0]
        self.unit_controller.load_unit(unit)
        unit._current_state = workflow.StateEnum.FINAL

        self.store_controller.save_file()

        assert _target_state(str(path), 'Open') == workflow.StateEnum.NEEDS_WORK

    def test_a_unit_without_states_loads_without_a_workflow(self, tmp_path):
        path = tmp_path / 'open.csv'
        path.write_bytes(CSV)
        self.store_controller.open_file(str(path))
        unit = self.store_controller.store.get_units()[0]

        view = self.unit_controller.load_unit(unit)

        assert view is self.unit_controller.view
        assert self.unit_controller.current_unit is unit
        assert not hasattr(unit, '_workflow')

    def test_get_unit_target_reads_the_target_shown(self, tmp_path):
        path = tmp_path / 'open.xlf'
        path.write_bytes(XLIFF)
        self.store_controller.open_file(str(path))
        self.unit_controller.load_unit(self.store_controller.store.get_units()[0])

        self.unit_controller.set_unit_target(0, ['Maak oop'])

        assert self.unit_controller.get_unit_target(0) == 'Maak oop'

    def test_a_paste_in_the_unit_view_is_announced_for_the_current_unit(self, tmp_path):
        path = tmp_path / 'open.xlf'
        path.write_bytes(XLIFF)
        self.store_controller.open_file(str(path))
        unit = self.store_controller.store.get_units()[0]
        self.unit_controller.load_unit(unit)
        pasted = []
        handler = self.unit_controller.connect('unit-paste-start', lambda _c, *args: pasted.append(args))
        try:
            self.unit_controller.view.emit('paste-start', 'Oop', (0, 3), 0)
        finally:
            self.unit_controller.disconnect(handler)

        assert pasted == [(unit, 'Oop', (0, 3), 0)]

    def test_finishing_without_a_current_unit_does_nothing(self):
        self.unit_controller.current_unit = None
        done = []
        handler = self.unit_controller.view.connect('unit-done', lambda *args: done.append(args))
        try:
            self.unit_controller.finish_current_unit()
        finally:
            self.unit_controller.view.disconnect(handler)

        assert done == []
        assert self.unit_controller.current_unit is None

    def test_unit_stats_without_a_store_are_left_alone(self):
        changed = []
        handler = self.store_controller.connect('stats-changed', lambda *args: changed.append(args))
        try:
            self.store_controller.update_unit_stats(object())
        finally:
            self.store_controller.disconnect(handler)

        assert changed == []
