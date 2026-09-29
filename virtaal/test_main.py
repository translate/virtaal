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
from virtaal.main import Virtaal, _Deferer, _resolve_startup_path

# _resolve_startup_path() #

def test_resolve_startup_path_leaves_a_plain_path_untouched():
    assert _resolve_startup_path('some.po') == 'some.po'


def test_resolve_startup_path_strips_a_posix_file_uri(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    assert _resolve_startup_path('file:///home/user/af.po') == '/home/user/af.po'


def test_resolve_startup_path_strips_a_windows_file_uri(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    assert _resolve_startup_path('file:///C:/translations/af.po') == 'C:/translations/af.po'


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


# Virtaal._open_startup_file() #

def test_open_startup_file_hides_the_loading_notice_and_defers_load_extras_on_success():
    v = Virtaal.__new__(Virtaal)
    v._open_with_file = lambda filename: True
    calls = []
    v.main_controller = SimpleNamespace(
        welcomescreen_controller=SimpleNamespace(activate=lambda: calls.append('activated')),
        view=SimpleNamespace(
            hide_loading_notice=lambda: calls.append('hidden'),
            show_startup_open_failure_notice=lambda f, r: calls.append(('shown', f, r))))
    deferred = []
    v.defer = lambda func, *args: deferred.append((func, args))

    v._open_startup_file('some.po')

    # No welcome screen re-activation and no failure notice on success -
    # only the loading notice (shown synchronously earlier by __init__)
    # gets torn down.
    assert calls == ['hidden']
    assert deferred == [(v._load_extras, ())]


def test_open_startup_file_shows_the_welcome_screen_and_failure_notice_with_the_reason_on_failure():
    v = Virtaal.__new__(Virtaal)
    v._open_with_file = lambda filename: False
    calls = []
    connected = []
    v.main_controller = SimpleNamespace(
        last_open_error='The file does not exist.',
        welcomescreen_controller=SimpleNamespace(activate=lambda: calls.append('activated')),
        store_controller=SimpleNamespace(connect=lambda signal, handler: connected.append((signal, handler))),
        view=SimpleNamespace(
            hide_loading_notice=lambda: calls.append('hidden'),
            show_startup_open_failure_notice=lambda f, r: calls.append(('shown', f, r)),
            hide_startup_open_failure_notice=lambda: calls.append('hidden-on-next-open')))
    deferred = []
    v.defer = lambda func, *args: deferred.append((func, args))

    v._open_startup_file('missing.po')

    assert calls == ['hidden', 'activated', ('shown', 'missing.po', 'The file does not exist.')]
    assert deferred == [(v._load_extras, ())]
    # A later successful open clears the notice instead of leaving it as
    # a stale reminder about a file the user has since moved past.
    assert [signal for signal, _handler in connected] == ['store-loaded']
    connected[0][1]()
    assert calls[-1] == 'hidden-on-next-open'


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


def _stub_virtaal_construction(monkeypatch, startupfile_exists=True):
    import virtaal.main as main_module
    monkeypatch.setattr('virtaal.support.crash_dialog.install', lambda: None)
    monkeypatch.setattr('gc.disable', lambda: None)
    monkeypatch.setattr(Virtaal, '_install_signal_handlers', lambda self: None)
    monkeypatch.setattr(main_module, '_Deferer', _FakeDeferer)
    monkeypatch.setattr('os.path.exists', lambda path: startupfile_exists)

    loading_notices = []
    failure_notices = []
    store_controller = SimpleNamespace()
    main_controller = SimpleNamespace(
        store_controller=store_controller,
        view=SimpleNamespace(
            show_loading_notice=lambda f: loading_notices.append(f),
            show_startup_open_failure_notice=lambda f, r: failure_notices.append((f, r))))
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

    return main_controller, welcome_instances, _FakeWelcomeScreenController, loading_notices, failure_notices


def test_init_without_a_startupfile_shows_the_welcome_screen_directly(monkeypatch):
    main_controller, welcome_instances, _FakeWSC, loading_notices, failure_notices = _stub_virtaal_construction(
        monkeypatch)

    v = Virtaal('')

    assert v.main_controller is main_controller
    assert len(welcome_instances) == 1
    assert welcome_instances[0].activated is True
    assert loading_notices == []
    assert v.defer.calls == [(v._open_with_welcome, ())]


def test_init_with_an_existing_startupfile_shows_a_loading_notice_instead_and_defers_the_open(monkeypatch):
    # WelcomeScreenController is constructed (needed for its
    # 'store-closed' handler later) but left un-activated here -
    # _open_startup_file (tested separately above) decides what to do
    # once the open resolves.
    main_controller, welcome_instances, _FakeWSC, loading_notices, failure_notices = _stub_virtaal_construction(
        monkeypatch, startupfile_exists=True)

    v = Virtaal('some.po')

    assert len(welcome_instances) == 1
    assert welcome_instances[0].activated is False
    assert loading_notices == ['some.po']
    assert failure_notices == []
    assert v.defer.calls == [(v._open_startup_file, ('some.po',))]


def test_init_with_a_missing_startupfile_skips_the_loading_notice_but_still_defers_the_real_open(monkeypatch):
    # _open_startup_file still runs unconditionally (tested separately
    # above) - only the loading-notice flash is skipped here.
    main_controller, welcome_instances, _FakeWSC, loading_notices, failure_notices = _stub_virtaal_construction(
        monkeypatch, startupfile_exists=False)

    v = Virtaal('missing.po')

    assert len(welcome_instances) == 1
    assert welcome_instances[0].activated is False
    assert loading_notices == []
    assert failure_notices == []
    assert v.defer.calls == [(v._open_startup_file, ('missing.po',))]
