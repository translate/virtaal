#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""ChecksController on a real store: choosing a checker and checking
units."""

from types import SimpleNamespace

import pytest
from translate.filters import checks

from virtaal.controllers import checkscontroller as checkscontroller_module
from virtaal.controllers.checkscontroller import ChecksController
from virtaal.controllers.langcontroller import LanguageController
from virtaal.test.test_scaffolding import TestScaffolding


def _toolkit_checker(checker):
    # Wrapped when the file gets extra checks (msgfmt's, with libgettextpo).
    return getattr(checker, 'checker', checker)


class TestChecksOnAStore(TestScaffolding):
    @pytest.fixture(autouse=True)
    def _store(self, monkeypatch):
        self.timers = []
        monkeypatch.setattr(checkscontroller_module.GLib, 'timeout_add',
                            lambda delay, func, *args, **kwargs: self.timers.append(lambda: func(*args)))
        self.store_controller.open_file(self.testfile[1])
        self.unit = self.store_controller.cursor.deref()
        self.unit_controller.load_unit(self.unit)
        self.checked = []
        self.checkers = []
        controller = self.checks_controller
        handlers = [
            controller.connect('unit-checked', lambda c, unit, checker, failures: self.checked.append(unit)),
            controller.connect('checker-set', lambda c, code: self.checkers.append(code)),
        ]
        yield
        for handler in handlers:
            controller.disconnect(handler)

    def test_choosing_a_checker_by_its_shown_name(self):
        self.checks_controller.set_checker_by_name('KDE')

        assert self.checks_controller.code == 'kde'
        assert isinstance(_toolkit_checker(self.checks_controller.get_checker()), checks.KdeChecker)
        assert self.checkers == ['kde']
        assert self.checks_controller.projview.btn_proj.get_label() == 'Checks: KDE'

    def test_an_unknown_name_chooses_the_default_checker(self):
        self.checks_controller.set_checker_by_name('No such project')

        assert self.checks_controller.code is None
        assert type(_toolkit_checker(self.checks_controller.get_checker())) is checks.StandardChecker

    def test_choosing_a_checker_checks_the_current_unit_again(self):
        self.checks_controller.set_checker_by_code('gnome')

        assert self.checked == [self.unit]

    def test_a_checker_without_a_target_language_checks_for_none(self, monkeypatch):
        monkeypatch.setattr(LanguageController, 'target_lang', property(lambda self: SimpleNamespace(code='')))

        self.checks_controller.set_checker_by_code('gnome')

        assert self.checks_controller.get_checker().config.targetlanguage is None

    def test_an_edit_checks_its_unit_after_a_delay(self):
        self.checks_controller.last_unit = self.unit

        self.checks_controller._start_check_timer()
        self.checks_controller._start_check_timer()  # One timer at a time.

        assert len(self.timers) == 1
        self.timers.pop()()
        assert self.checked == [self.unit]
        assert not self.checks_controller._check_timer_active

    def test_a_delayed_check_skips_a_unit_already_left(self):
        self.checks_controller.last_unit = self.unit
        self.checks_controller._start_check_timer()
        self.checks_controller.last_unit = object()

        self.timers.pop()()

        assert self.checked == []

    def test_no_delayed_check_before_any_unit(self):
        self.checks_controller.last_unit = None

        self.checks_controller._start_check_timer()

        assert self.timers == []
        assert not self.checks_controller._check_timer_active

    def test_an_unknown_checks_name_is_shown_as_is(self):
        assert self.checks_controller.get_check_name('no-such-check') == 'no-such-check'
        assert self.checks_controller.get_check_name('check-no-such-check') == 'no-such-check'

    def test_a_controller_started_after_a_store_opens_checks_it(self):
        started = ChecksController(self.main_controller)
        try:
            assert started.get_checker() is not None
            assert started.last_unit is self.unit
        finally:
            self.main_controller.checks_controller = self.checks_controller
