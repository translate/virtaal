#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import pan_app
from virtaal.controllers.prefscontroller import PreferencesController


class _FakeSettings:
    def __init__(self, uilang=''):
        self.language = {'sourcefont': '', 'targetfont': '', 'uilang': uilang}
        self.translator = {'name': '', 'email': '', 'team': ''}


class _FakeUnitControllerView:
    def update_languages(self):
        pass


class _FakeMainControllerView:
    def __init__(self):
        self.language_change_notices = 0

    def show_language_change_notice(self):
        self.language_change_notices += 1


class _FakeMainController:
    def __init__(self):
        self.unit_controller = type('_UC', (), {'view': _FakeUnitControllerView()})()
        self.view = _FakeMainControllerView()


class _FakeView:
    def __init__(self, ui_language):
        self.font_data = {'source': '', 'target': ''}
        self.user_data = {'name': '', 'email': '', 'team': ''}
        self.ui_language = ui_language


def _make_controller(monkeypatch, saved_uilang):
    monkeypatch.setattr(pan_app, 'settings', _FakeSettings(uilang=saved_uilang))
    controller = PreferencesController.__new__(PreferencesController)
    controller.main_controller = _FakeMainController()
    return controller


def test_prefs_done_saves_a_changed_ui_language(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert pan_app.settings.language['uilang'] == 'af'


def test_prefs_done_shows_a_restart_notice_when_the_language_changed(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert controller.main_controller.view.language_change_notices == 1


def test_prefs_done_does_nothing_when_the_language_is_unchanged(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='af')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert pan_app.settings.language['uilang'] == 'af'
    assert controller.main_controller.view.language_change_notices == 0


def test_update_language_gui_data_reads_the_saved_setting(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='fr')
    controller.view = _FakeView(ui_language='')

    controller._update_language_gui_data()

    assert controller.view.ui_language == 'fr'
