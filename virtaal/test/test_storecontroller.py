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

    def _update_from_template(self, tmp_path):
        """Open the test file, update it from a template that changes
        its counts, and return the notice with the counts."""
        template = tmp_path / 'new.pot'
        template.write_text('msgid "Only this"\nmsgstr ""\n', encoding='utf-8')
        self.store_controller.open_file(self.testfile[1])
        self.main_controller.update_file(str(template))
        notice = self.main_controller.view._template_update_infobar
        vbox_main = self.main_controller.view.gui.get_object('vbox_main')
        assert notice is not None and notice.get_parent() is vbox_main
        return notice

    def test_the_update_from_template_notice_goes_when_another_file_opens(self, tmp_path):
        other = tmp_path / 'other.po'
        other.write_text('msgid "Other"\nmsgstr "Ander"\n', encoding='utf-8')
        notice = self._update_from_template(tmp_path)

        self.store_controller.open_file(str(other))

        assert self.main_controller.view._template_update_infobar is None
        assert notice.get_parent() is None

    def test_the_update_from_template_notice_goes_when_the_file_closes(self, tmp_path):
        notice = self._update_from_template(tmp_path)

        self.store_controller.close_file()

        assert self.main_controller.view._template_update_infobar is None
        assert notice.get_parent() is None
