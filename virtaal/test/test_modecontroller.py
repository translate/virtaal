#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from unittest.mock import MagicMock

from test_scaffolding import TestScaffolding


class TestModeController(TestScaffolding):
    def test_get_mode_by_display_name(self):
        default_mode_display_name = self.mode_controller.modenames['Default']
        default_mode = self.mode_controller.get_mode_by_display_name(default_mode_display_name)
        assert default_mode == self.mode_controller.modes[self.mode_controller.default_mode_name]

    def test_reselecting_menu_modes_destroys_previous_popup(self):
        """Regression test for Release Blocker #8: WorkflowMode and
        QualityCheckMode each build a fresh Gtk.Menu (with real
        Gtk.CheckMenuItem children) every time they're selected - the
        previous one must be destroy()ed deterministically, not just
        dropped for Python's GC to collect (see their own
        _add_widgets() comment for why relying on GC caused a native
        segfault)."""
        self.store_controller.open_file(self.testfile[1])
        default_mode = self.mode_controller.modes[self.mode_controller.default_mode_name]

        for name in ('Workflow', 'QualityCheck'):
            mode = self.mode_controller.modes[name]

            self.mode_controller.select_mode(mode)
            old_button = mode.btn_popup
            old_menu = old_button.menu
            old_button.destroy = MagicMock()
            old_menu.destroy = MagicMock()

            self.mode_controller.select_mode(default_mode)
            self.mode_controller.select_mode(mode)

            assert old_button.destroy.called, '%s: previous popup button was not destroyed' % (name)
            assert old_menu.destroy.called, '%s: previous popup menu was not destroyed' % (name)

    def test_select_mode(self):
        self.store_controller.open_file(self.testfile[1])
        for name, mode in self.mode_controller.modes.items():
            self.mode_controller.select_mode(mode)
            assert self.mode_controller.current_mode is mode

    def test_select_mode_by_name(self):
        self.store_controller.open_file(self.testfile[1])
        for name, mode in self.mode_controller.modes.items():
            self.mode_controller.select_mode_by_name(name)
            assert self.mode_controller.current_mode is mode
