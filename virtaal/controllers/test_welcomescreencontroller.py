#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.controllers.welcomescreencontroller import WelcomeScreenController


def test_open_bug_report_opens_the_prefilled_template(monkeypatch):
    from virtaal.support import openmailto

    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))

    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller.open_bug_report()

    assert len(opened) == 1
    assert opened[0].startswith(
        'https://github.com/translate/virtaal/issues/new?')
    assert 'template=bug_report.yml' in opened[0]


class _FakeView:
    def __init__(self, controller):
        self.controller = controller
        self.shown = False
        self.hidden = False
        self.recent_buttons = None

    def show(self):
        self.shown = True

    def hide(self):
        self.hidden = True

    def update_recent_buttons(self, recent_files):
        self.recent_buttons = recent_files


class _FakeStoreController:
    def __init__(self):
        self.connected = []

    def connect(self, signal, handler):
        self.connected.append((signal, handler))
        return len(self.connected)


def test_init_wires_the_view_and_store_signals(monkeypatch):
    monkeypatch.setattr('virtaal.views.welcomescreenview.WelcomeScreenView', _FakeView)
    main_controller = SimpleNamespace(store_controller=_FakeStoreController())

    controller = WelcomeScreenController(main_controller)

    assert main_controller.welcomescreen_controller is controller
    assert controller._recent_files == []
    assert controller.view.controller is controller
    signals = [s for s, _handler in main_controller.store_controller.connected]
    assert signals == ['store-closed', 'store-loaded']


def test_activate_shows_the_view_and_schedules_a_recent_files_refresh(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('gi.repository.GLib.idle_add', lambda func, **kw: idle_calls.append((func, kw)))
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller.view = _FakeView(controller)

    controller.activate()

    assert controller.view.shown
    assert len(idle_calls) == 1
    func, kwargs = idle_calls[0]
    assert func == controller.update_recent


def test_open_cheatsheat_opens_a_shortcuts_window():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller.main_controller = SimpleNamespace(view=SimpleNamespace(main_window=Gtk.Window()))

    controller.open_cheatsheat()  # must not raise


def test_open_file_delegates_to_the_main_controller():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    calls = []
    controller.main_controller = SimpleNamespace(open_file=lambda filename: calls.append(filename))

    controller.open_file('/tmp/x.po')

    assert calls == ['/tmp/x.po']


def test_open_recent_opens_the_file_at_the_given_position():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller._recent_files = [{'uri': 'a'}, {'uri': 'b'}, {'uri': 'c'}]
    calls = []
    controller.open_file = lambda uri: calls.append(uri)

    controller.open_recent(2)  # nominal 1-5, so index 1

    assert calls == ['b']


def test_open_recent_ignores_an_out_of_range_index():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller._recent_files = [{'uri': 'a'}]
    calls = []
    controller.open_file = lambda uri: calls.append(uri)

    controller.open_recent(5)

    assert calls == []


def test_open_recent_ignores_index_zero():
    # Nominal range is [1; 5] - 0 shifts to -1, outside the valid [0; N-1].
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller._recent_files = [{'uri': 'a'}]
    calls = []
    controller.open_file = lambda uri: calls.append(uri)

    controller.open_recent(0)

    assert calls == []


def test_open_tutorial_delegates_to_the_main_controller():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    calls = []
    controller.main_controller = SimpleNamespace(open_tutorial=lambda: calls.append(True))

    controller.open_tutorial()

    assert calls == [True]


def test_try_open_link_opens_a_known_link(monkeypatch):
    from virtaal.support import openmailto

    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    controller = WelcomeScreenController.__new__(WelcomeScreenController)

    result = controller.try_open_link('manual')

    assert result is True
    assert opened == [WelcomeScreenController.LINKS['manual']]


def test_try_open_link_rejects_an_unknown_link(monkeypatch):
    from virtaal.support import openmailto

    opened = []
    monkeypatch.setattr(openmailto, 'open', lambda url: opened.append(url))
    controller = WelcomeScreenController.__new__(WelcomeScreenController)

    result = controller.try_open_link('nonexistent')

    assert result is False
    assert opened == []


class _FakeRecentItem:
    def __init__(self, name, uri):
        self._name = name
        self._uri = uri

    def get_display_name(self):
        return self._name

    def get_uri_display(self):
        return self._uri


def test_update_recent_truncates_to_max_recent(monkeypatch):
    items = [_FakeRecentItem(f'name{i}', f'uri{i}') for i in range(10)]
    monkeypatch.setattr('virtaal.views.recent.rc.get_items', lambda: items)
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller.view = _FakeView(controller)

    controller.update_recent()

    assert len(controller._recent_files) == WelcomeScreenController.MAX_RECENT
    assert controller._recent_files[0] == {'name': 'name0', 'uri': 'uri0'}
    assert controller.view.recent_buttons == controller._recent_files


def test_on_store_closed_activates_the_welcome_screen(monkeypatch):
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    calls = []
    controller.activate = lambda: calls.append(True)

    controller._on_store_closed(None)

    assert calls == [True]


def test_on_store_loaded_hides_the_view():
    controller = WelcomeScreenController.__new__(WelcomeScreenController)
    controller.view = _FakeView(controller)

    controller._on_store_loaded(None)

    assert controller.view.hidden
