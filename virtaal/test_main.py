#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import signal
from types import SimpleNamespace

import pytest
from gi.repository import GLib

from virtaal.common import pan_app
from virtaal.common.platform import platform
from virtaal.main import Virtaal, _Deferer


def _deferer(monkeypatch):
    monkeypatch.setattr(_Deferer, '_todo', [])
    return _Deferer()


def test_defer_schedules_idle_add_only_once_for_the_first_job(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))

    defer(lambda: None)
    defer(lambda: None)

    assert len(scheduled) == 1


def test_defer_runs_queued_jobs_in_order(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    ran = []

    defer(ran.append, 'first')
    defer(ran.append, 'second')
    next_job = scheduled[0]

    still_more = next_job()
    assert ran == ['first']
    assert still_more is True

    still_more = next_job()
    assert ran == ['first', 'second']
    assert still_more is False


def test_next_job_tolerates_being_called_with_an_already_empty_queue(monkeypatch):
    # Documented edge case: a previous next_job() call can be the last
    # one queued in the event loop even though the job it ran added
    # more work - a second, now-redundant next_job() may still fire.
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    defer(lambda: None)
    next_job = scheduled[0]
    next_job()  # drains the only job

    assert next_job() is False  # must not raise IndexError


def test_a_job_that_defers_more_work_schedules_a_fresh_idle_source(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    ran = []

    def first_job():
        ran.append('first')
        # The queue is empty at this exact point (this job was already
        # popped) - defer() here must schedule a new idle source rather
        # than assume one is still pending.
        defer(ran.append, 'second')

    defer(first_job)
    scheduled[0]()

    assert len(scheduled) == 2
    scheduled[1]()
    assert ran == ['first', 'second']


# Virtaal._install_signal_handlers() #

def _fake_glib(unix_signal_add):
    # Replaces the whole GLib binding main.py sees, rather than
    # monkeypatching GLib.unix_signal_add directly - PyGObject flags
    # that symbol deprecated via a __getattr__ override that warns on
    # any *access*, including monkeypatch's own save-the-old-value
    # read, which would otherwise trip this suite's
    # unlisted-deprecation-warning gate on a pre-existing call this
    # file already makes for real, unrelated to what's under test here.
    return SimpleNamespace(
        PRIORITY_DEFAULT=GLib.PRIORITY_DEFAULT,
        SOURCE_REMOVE=GLib.SOURCE_REMOVE,
        unix_signal_add=unix_signal_add,
    )


def test_install_signal_handlers_does_nothing_on_windows(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr('virtaal.main.GLib', _fake_glib(
        unix_signal_add=lambda *a: pytest.fail('must not register a signal on Windows')))
    v = Virtaal.__new__(Virtaal)

    v._install_signal_handlers()  # must not raise


def test_install_signal_handlers_registers_sigterm_and_sigint(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    registered = []
    monkeypatch.setattr('virtaal.main.GLib', _fake_glib(
        unix_signal_add=lambda priority, sig, handler, s: registered.append((sig, handler))))
    v = Virtaal.__new__(Virtaal)

    v._install_signal_handlers()

    assert [sig for sig, handler in registered] == [signal.SIGTERM, signal.SIGINT]


def test_signal_handler_forces_a_quit_and_removes_its_own_source(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    handlers = []
    monkeypatch.setattr('virtaal.main.GLib', _fake_glib(
        unix_signal_add=lambda priority, sig, handler, s: handlers.append(handler)))
    v = Virtaal.__new__(Virtaal)
    quit_calls = []
    v.main_controller = SimpleNamespace(quit=lambda force: quit_calls.append(force))

    v._install_signal_handlers()
    result = handlers[0](signal.SIGTERM)

    assert quit_calls == [True]
    assert result == GLib.SOURCE_REMOVE


# Virtaal._open_with_file() / ._open_with_welcome() #

def test_open_with_file_constructs_controllers_in_order_and_opens_the_file(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'virtaal.controllers.unitcontroller.UnitController', lambda sc: calls.append(('unit', sc)))
    monkeypatch.setattr(
        'virtaal.controllers.modecontroller.ModeController', lambda mc: calls.append(('mode', mc)))
    monkeypatch.setattr(
        'virtaal.controllers.langcontroller.LanguageController', lambda mc: calls.append(('lang', mc)))
    monkeypatch.setattr(
        'virtaal.controllers.placeablescontroller.PlaceablesController', lambda mc: calls.append(('placeables', mc)))
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(
        store_controller='store-controller', open_file=lambda f: calls.append(('open', f)) or 'opened')

    result = v._open_with_file('some.po')

    assert calls == [
        ('unit', 'store-controller'), ('mode', v.main_controller), ('lang', v.main_controller),
        ('placeables', v.main_controller), ('open', 'some.po'),
    ]
    assert result == 'opened'


def test_open_with_welcome_defers_controller_construction_and_load_extras():
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(store_controller='store-controller')
    deferred = []
    v.defer = lambda func, *args: deferred.append((func, args))

    v._open_with_welcome()

    from virtaal.controllers.langcontroller import LanguageController
    from virtaal.controllers.modecontroller import ModeController
    from virtaal.controllers.placeablescontroller import PlaceablesController
    from virtaal.controllers.unitcontroller import UnitController
    assert deferred == [
        (UnitController, ('store-controller',)), (ModeController, (v.main_controller,)),
        (LanguageController, (v.main_controller,)), (PlaceablesController, (v.main_controller,)),
        (v._load_extras, ()),
    ]


# Virtaal._load_extras() #

def test_load_extras_defers_the_remaining_controllers_and_config_recovery(monkeypatch):
    monkeypatch.setattr(platform, 'is_frozen', False)
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(load_plugins='load-plugins')
    deferred = []
    v.defer = lambda func, *args: deferred.append((func, args))

    v._load_extras()

    from virtaal.controllers.checkscontroller import ChecksController
    from virtaal.controllers.plugincontroller import PluginController
    from virtaal.controllers.prefscontroller import PreferencesController
    from virtaal.controllers.propertiescontroller import PropertiesController
    from virtaal.controllers.undocontroller import UndoController
    from virtaal.support.dictionary_download_watcher import DictionaryDownloadWatcher
    funcs = [f for f, a in deferred]
    assert funcs == [
        ChecksController, UndoController, PluginController, PreferencesController,
        PropertiesController, DictionaryDownloadWatcher, 'load-plugins', v._check_for_config_recovery,
    ]


def test_load_extras_also_defers_the_update_check_when_frozen(monkeypatch):
    monkeypatch.setattr(platform, 'is_frozen', True)
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(load_plugins=lambda: None)
    deferred = []
    v.defer = lambda func, *args: deferred.append((func, args))

    v._load_extras()

    assert v._check_for_update in [f for f, a in deferred]


# Virtaal._check_for_config_recovery() / ._check_for_update() #

def test_check_for_config_recovery_shows_the_notice_when_a_backup_exists(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'config_recovery_backup', '/tmp/backup.ini')
    v = Virtaal.__new__(Virtaal)
    shown = []
    v.main_controller = SimpleNamespace(view=SimpleNamespace(show_config_recovery_notice=shown.append))

    v._check_for_config_recovery()

    assert shown == ['/tmp/backup.ini']


def test_check_for_config_recovery_does_nothing_without_a_backup(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'config_recovery_backup', '')
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(view=SimpleNamespace(
        show_config_recovery_notice=lambda p: pytest.fail('must not show without a backup')))

    v._check_for_config_recovery()


def test_check_for_update_runs_the_update_checker(monkeypatch):
    calls = []

    class _FakeUpdateChecker:
        def __init__(self, ver, callback):
            calls.append(('init', ver, callback))

        def check(self):
            calls.append('checked')
    monkeypatch.setattr('virtaal.support.update_check.UpdateChecker', _FakeUpdateChecker)
    v = Virtaal.__new__(Virtaal)
    v.main_controller = SimpleNamespace(view=SimpleNamespace(show_update_notice='show-update-notice'))

    v._check_for_update()

    assert calls[0][2] == 'show-update-notice'
    assert calls[1] == 'checked'


# Virtaal.run() #

def test_run_runs_and_destroys_the_main_controller():
    v = Virtaal.__new__(Virtaal)
    calls = []
    v.main_controller = SimpleNamespace(run=lambda: calls.append('run'), destroy=lambda: calls.append('destroy'))

    v.run()

    assert calls == ['run', 'destroy']
    assert not hasattr(v, 'main_controller')


# Virtaal.__init__() #

class _FakeDeferer:
    def __init__(self):
        self.calls = []

    def __call__(self, func, *args):
        self.calls.append((func, args))


def _stub_virtaal_construction(monkeypatch, open_file_result=None):
    import virtaal.main as main_module
    monkeypatch.setattr('virtaal.support.crash_dialog.install', lambda: None)
    monkeypatch.setattr('gc.disable', lambda: None)
    monkeypatch.setattr(Virtaal, '_install_signal_handlers', lambda self: None)
    # _open_with_file()/._open_with_welcome() have their own dedicated
    # tests above - stub them here so __init__'s own branching is what
    # this test actually exercises.
    monkeypatch.setattr(Virtaal, '_open_with_file', lambda self, filename: open_file_result)
    monkeypatch.setattr(main_module, '_Deferer', _FakeDeferer)

    store_controller = SimpleNamespace()
    main_controller = SimpleNamespace(store_controller=store_controller)
    monkeypatch.setattr('virtaal.controllers.maincontroller.MainController', lambda: main_controller)
    monkeypatch.setattr('virtaal.controllers.storecontroller.StoreController', lambda mc: store_controller)

    welcome_instances = []

    class _FakeWelcomeScreenController:
        def __init__(self, mc):
            self.main_controller = mc
            self.activated = False
            welcome_instances.append(self)

        def activate(self):
            self.activated = True
    monkeypatch.setattr(
        'virtaal.controllers.welcomescreencontroller.WelcomeScreenController', _FakeWelcomeScreenController)

    return main_controller, welcome_instances, _FakeWelcomeScreenController


def test_init_without_a_startupfile_shows_the_welcome_screen_directly(monkeypatch):
    main_controller, welcome_instances, _FakeWSC = _stub_virtaal_construction(monkeypatch)

    v = Virtaal('')

    assert v.main_controller is main_controller
    assert len(welcome_instances) == 1
    assert welcome_instances[0].activated is True
    assert v.defer.calls == [(v._open_with_welcome, ())]


def test_init_with_a_startupfile_that_opens_successfully_defers_the_welcome_screen(monkeypatch):
    main_controller, welcome_instances, _FakeWSC = _stub_virtaal_construction(monkeypatch, open_file_result=True)

    v = Virtaal('some.po')

    assert welcome_instances == []  # not shown directly - only via the deferred call below
    assert v.defer.calls == [
        (_FakeWSC, (main_controller,)),
        (v._load_extras, ()),
    ]


def test_init_with_a_startupfile_that_fails_to_open_shows_the_welcome_screen_directly(monkeypatch):
    main_controller, welcome_instances, _FakeWSC = _stub_virtaal_construction(monkeypatch, open_file_result=False)

    v = Virtaal('missing.po')

    assert len(welcome_instances) == 1
    assert welcome_instances[0].activated is True
    assert v.defer.calls == [(v._load_extras, ())]
