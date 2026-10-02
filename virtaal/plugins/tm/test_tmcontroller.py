#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest

from virtaal.plugins.tm.tmcontroller import TMController


def _bare_controller(**overrides):
    controller = TMController.__new__(TMController)
    for name, value in overrides.items():
        setattr(controller, name, value)
    return controller


class _FakePlugin:
    """A plain, hashable stand-in for a plugin - unlike SimpleNamespace,
    whose own __eq__ makes it unusable as a dict key."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _make_controller(matches=None, max_matches=5, current_query='hello', storecursor=True):
    controller = TMController.__new__(TMController)
    controller.storecursor = storecursor
    controller.current_query = current_query
    controller.matches = matches if matches is not None else []
    controller.max_matches = max_matches
    controller.displayed = []
    controller.view = SimpleNamespace(display_matches=lambda matches: controller.displayed.append(list(matches)))
    return controller


def _tmmodel(display_name='Some TM'):
    return SimpleNamespace(display_name=display_name)


def test_accept_response_ignores_a_response_after_the_file_was_closed():
    controller = _make_controller(storecursor=None)

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches == []
    assert controller.displayed == []


def test_accept_response_ignores_a_stale_query():
    controller = _make_controller(current_query='goodbye')

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches == []


def test_accept_response_ignores_an_empty_matches_list():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [])

    assert controller.matches == []
    assert controller.displayed == []


def test_accept_response_coerces_a_string_quality_to_int():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': '90'}])

    assert controller.matches[0]['quality'] == 90


def test_accept_response_defaults_a_missing_tmsource_to_the_models_display_name():
    controller = _make_controller()

    controller.accept_response(_tmmodel('Amagama'), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches[0]['tmsource'] == 'Amagama'


def test_accept_response_adds_a_genuinely_new_match_and_displays_it():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert len(controller.matches) == 1
    assert controller.displayed == [controller.matches]


def test_accept_response_keeps_an_existing_qualified_match_over_a_duplicate_target():
    """A duplicate suggestion (same normalized target) that already has
        quality information is trusted over a new one - only a
        qualityless existing match (e.g. from MT) gets replaced."""
    existing = {'target': 'hallo', 'quality': 95, 'tmsource': 'Local TM', 'query_str': 'hello'}
    controller = _make_controller(matches=[existing])

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 80}])

    assert controller.matches == [existing]
    assert controller.displayed == []  # nothing new, so display_matches is never called


def test_accept_response_replaces_an_unqualified_duplicate_with_a_qualified_one():
    existing = {'target': 'hallo', 'quality': None, 'tmsource': 'Machine Translation', 'query_str': 'hello'}
    controller = _make_controller(matches=[existing])

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert len(controller.matches) == 1
    assert controller.matches[0]['quality'] == 90
    assert existing not in controller.matches


def test_accept_response_sorts_by_quality_descending_and_truncates_to_max_matches():
    controller = _make_controller(max_matches=2)

    controller.accept_response(_tmmodel(), 'hello', [
        {'target': 'laag', 'quality': 60},
        {'target': 'hoog', 'quality': 95},
        {'target': 'middel', 'quality': 80},
    ])

    assert [m['target'] for m in controller.matches] == ['hoog', 'middel']


# __init__() #

def test_init_computes_config_and_delegates_to_helpers(monkeypatch):
    calls = []
    monkeypatch.setattr(TMController, '_load_models', lambda self: calls.append('load_models'))
    monkeypatch.setattr(TMController, '_connect_plugin', lambda self: calls.append('connect_plugin'))
    fake_view = SimpleNamespace()
    monkeypatch.setattr('virtaal.plugins.tm.tmview.TMView', lambda controller, max_matches: fake_view)
    main_controller = object()

    controller = TMController(main_controller, config={'max_matches': 3, 'min_quality': 50, 'disabled_models': ['foo']})

    assert controller.main_controller is main_controller
    assert controller.max_matches == 3
    assert controller.min_quality == 50
    assert controller.disabled_model_names == ['basetmmodel', 'foo']
    assert controller.storecursor is None
    assert controller.view is fake_view
    assert calls == ['load_models', 'connect_plugin']


def test_init_defaults_config_when_none_given(monkeypatch):
    monkeypatch.setattr(TMController, '_load_models', lambda self: None)
    monkeypatch.setattr(TMController, '_connect_plugin', lambda self: None)
    monkeypatch.setattr('virtaal.plugins.tm.tmview.TMView', lambda controller, max_matches: SimpleNamespace())

    controller = TMController(object())

    assert controller.config == {}
    assert controller.max_matches == 5
    assert controller.min_quality == 75
    assert controller.disabled_model_names == ['basetmmodel']


# _load_models() #

def test_load_models_builds_the_plugin_controller_and_loads_plugins(monkeypatch):
    controller = _bare_controller(disabled_model_names=['x', 'y'], _signal_ids={})
    captured = {}

    def fake_for_backend(owner, classname, category, interface, get_disabled):
        captured['args'] = (owner, classname, category, interface, get_disabled)
        return SimpleNamespace(connect=lambda signal, handler: f'sig-{signal}', load_plugins=lambda: calls.append('loaded'))
    calls = []
    monkeypatch.setattr('virtaal.controllers.plugincontroller.PluginController.for_backend', fake_for_backend)

    controller._load_models()

    owner, classname, category, interface, get_disabled = captured['args']
    assert (owner, classname, category) == (controller, 'TMModel', 'tm')
    assert get_disabled() == ['x', 'y']
    assert calls == ['loaded']
    assert controller._signal_ids['plugin-enabled'] == 'sig-plugin-enabled'
    assert controller._signal_ids['plugin-disabled'] == 'sig-plugin-disabled'


def test_load_models_on_plugin_enabled_connects_match_found_to_accept_response(monkeypatch):
    controller = _bare_controller(disabled_model_names=[], _signal_ids={})
    handlers = {}
    monkeypatch.setattr(
        'virtaal.controllers.plugincontroller.PluginController.for_backend',
        lambda *a: SimpleNamespace(
            connect=lambda signal, handler: handlers.__setitem__(signal, handler) or f'sig-{signal}',
            load_plugins=lambda: None,
        ),
    )
    controller._load_models()
    plugin = _FakePlugin(connect=lambda signal, handler: 'plugin-sig')

    handlers['plugin-enabled'](None, plugin)

    assert controller._model_signal_ids[plugin] == 'plugin-sig'


def test_load_models_on_plugin_disabled_disconnects_the_model(monkeypatch):
    controller = _bare_controller(disabled_model_names=[], _signal_ids={})
    handlers = {}
    monkeypatch.setattr(
        'virtaal.controllers.plugincontroller.PluginController.for_backend',
        lambda *a: SimpleNamespace(
            connect=lambda signal, handler: handlers.__setitem__(signal, handler) or f'sig-{signal}',
            load_plugins=lambda: None,
        ),
    )
    controller._load_models()
    disconnected = []
    plugin = _FakePlugin(disconnect=disconnected.append)
    controller._model_signal_ids[plugin] = 'plugin-sig'

    handlers['plugin-disabled'](None, plugin)

    assert disconnected == ['plugin-sig']


# _connect_plugin() #

def _fake_store_controller(store=None):
    connected = []

    def connect(signal, handler):
        connected.append(signal)
        return f'sig-{signal}'
    sc = SimpleNamespace(connect=connect, get_store=lambda: store)
    sc._connected = connected
    return sc


def test_connect_plugin_subscribes_to_store_loaded_and_closed():
    controller = _bare_controller()
    store_controller = _fake_store_controller(store=None)
    controller.main_controller = SimpleNamespace(store_controller=store_controller, mode_controller=None)

    controller._connect_plugin()

    assert store_controller._connected == ['store-loaded', 'store-closed']
    assert controller._store_loaded_id == 'sig-store-loaded'
    assert controller._store_closed_id == 'sig-store-closed'


def test_connect_plugin_immediately_loads_an_already_open_store():
    controller = _bare_controller()
    calls = []
    controller._on_store_loaded = lambda sc: calls.append(sc)
    store_controller = _fake_store_controller(store=object())
    controller.main_controller = SimpleNamespace(store_controller=store_controller, mode_controller=None)
    controller.view = SimpleNamespace(_should_show_tmwindow=False)

    controller._connect_plugin()

    assert calls == [store_controller]
    assert controller.view._should_show_tmwindow is True


def test_connect_plugin_subscribes_to_mode_selected_when_a_mode_controller_exists():
    controller = _bare_controller()
    store_controller = _fake_store_controller()
    mode_controller = SimpleNamespace(connect=lambda signal, handler: 'sig-' + signal)
    controller.main_controller = SimpleNamespace(store_controller=store_controller, mode_controller=mode_controller)

    controller._connect_plugin()

    assert controller._mode_selected_id == 'sig-mode-selected'
    assert controller._context_selected_id == 'sig-context-selected'


def test_connect_plugin_skips_mode_selected_without_a_mode_controller():
    controller = _bare_controller()
    store_controller = _fake_store_controller()
    controller.main_controller = SimpleNamespace(store_controller=store_controller, mode_controller=None)

    controller._connect_plugin()

    assert not hasattr(controller, '_mode_selected_id')


# destroy() #

def test_destroy_tears_down_the_view_and_all_registered_signals():
    controller = _bare_controller()
    calls = []
    controller.view = SimpleNamespace(hide=lambda: calls.append('hide'), destroy=lambda: calls.append('destroy'))
    store_controller = SimpleNamespace(disconnect=lambda sid: calls.append(('store', sid)))
    store_controller.cursor = SimpleNamespace(disconnect=lambda sid: calls.append(('cursor', sid)))
    mode_controller = SimpleNamespace(disconnect=lambda sid: calls.append(('mode', sid)))
    unit_controller = SimpleNamespace(view=SimpleNamespace(disconnect=lambda sid: calls.append(('target', sid))))
    controller.main_controller = SimpleNamespace(
        store_controller=store_controller, mode_controller=mode_controller, unit_controller=unit_controller,
    )
    controller._store_loaded_id = 'store-id'
    controller._cursor_changed_id = 'cursor-id'
    controller._mode_selected_id = 'mode-id'
    controller._context_selected_id = 'context-id'
    controller._target_focused_id = 'target-id'
    controller._completion_toggled_id = 'completion-id'
    controller.plugin_controller = SimpleNamespace(shutdown=lambda: calls.append('shutdown'))

    controller.destroy()

    assert calls == [
        'hide', 'destroy', ('store', 'store-id'), ('cursor', 'cursor-id'),
        ('mode', 'mode-id'), ('mode', 'context-id'), ('target', 'target-id'), ('target', 'completion-id'),
        'shutdown',
    ]


def test_destroy_skips_optional_signals_that_were_never_connected():
    controller = _bare_controller()
    calls = []
    controller.view = SimpleNamespace(hide=lambda: calls.append('hide'), destroy=lambda: calls.append('destroy'))
    controller.main_controller = SimpleNamespace(
        store_controller=SimpleNamespace(disconnect=lambda sid: calls.append(('store', sid))),
    )
    controller._store_loaded_id = 'store-id'
    controller.plugin_controller = SimpleNamespace(shutdown=lambda: calls.append('shutdown'))

    controller.destroy()

    assert calls == ['hide', 'destroy', ('store', 'store-id'), 'shutdown']


# select_match() #

def test_select_match_pushes_undo_and_sets_the_focused_target():
    controller = _bare_controller()
    calls = []
    view = SimpleNamespace(focused_target_n=1, get_target_n=lambda n: 'old text', targets=['textbox0', 'textbox1'])
    unit_controller = SimpleNamespace(view=view, set_unit_target=lambda n, text: calls.append(('set', n, text)))
    controller.main_controller = SimpleNamespace(
        unit_controller=unit_controller,
        undo_controller=SimpleNamespace(push_current_text=lambda textbox: calls.append(('push', textbox))),
    )

    controller.select_match({'target': 'hallo'})

    assert calls == [('push', 'textbox1'), ('set', 1, 'hallo')]


# send_tm_query() #

def test_send_tm_query_uses_the_given_unit_and_clears_previous_matches():
    controller = _bare_controller(matches=['stale'])
    calls = []
    controller.view = SimpleNamespace(clear=lambda: calls.append('clear'))
    emitted = []
    controller.emit = lambda signal, unit: emitted.append((signal, unit))
    unit = SimpleNamespace(source='hello')

    controller.send_tm_query(unit)

    assert controller.unit is unit
    assert controller.current_query == 'hello'
    assert controller.matches == []
    assert calls == ['clear']
    assert emitted == [('start-query', unit)]


def test_send_tm_query_reuses_the_existing_unit_when_none_given():
    controller = _bare_controller(unit=SimpleNamespace(source='bye'))
    controller.view = SimpleNamespace(clear=lambda: None)
    controller.emit = lambda *a: None

    controller.send_tm_query()

    assert controller.current_query == 'bye'


# start_query() #

def test_start_query_does_nothing_without_a_store_cursor():
    controller = _bare_controller(storecursor=None)

    controller.start_query()  # must not raise


def _controller_for_start_query(**overrides):
    overrides.setdefault('_delay_id', None)
    controller = _bare_controller(storecursor=SimpleNamespace(deref=lambda: pytest.fail('must not re-derive a cached unit')), **overrides)
    controller.view = SimpleNamespace(hide=lambda: None)
    return controller


def test_start_query_uses_the_cached_unit_when_already_set(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.timeout_add', lambda delay, cb: scheduled.append((delay, cb)) or 'timeout-id')
    controller = _controller_for_start_query(unit=SimpleNamespace(source='x'))
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=SimpleNamespace(connect=lambda signal, handler: 'sig-' + signal)))

    controller.start_query()

    assert controller._target_focused_id == 'sig-target-focused'
    assert controller._completion_toggled_id == 'sig-completion-popup-toggled'
    assert scheduled and scheduled[0][0] == TMController.QUERY_DELAY


def test_start_query_derives_the_unit_from_the_cursor_when_none_cached(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.timeout_add', lambda delay, cb: 'timeout-id')
    controller = _bare_controller(storecursor=SimpleNamespace(deref=lambda: 'derived-unit'), _delay_id=None)
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=SimpleNamespace(connect=lambda *a: 'sig')))
    controller.view = SimpleNamespace(hide=lambda: None)

    controller.start_query()

    assert controller.unit == 'derived-unit'


def test_start_query_disconnects_a_previous_target_focused_subscription(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.timeout_add', lambda delay, cb: 'timeout-id')
    disconnected = []
    unit_view = SimpleNamespace(connect=lambda signal, handler: 'new-sig', disconnect=disconnected.append)
    controller = _controller_for_start_query(unit='cached', _target_focused_id='old-sig')
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=unit_view))

    controller.start_query()

    assert disconnected == ['old-sig']
    assert controller._target_focused_id == 'new-sig'


def test_start_query_cancels_a_pending_delayed_query_before_scheduling_a_new_one(monkeypatch):
    removed = []
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.source_remove', removed.append)
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.timeout_add', lambda delay, cb: 'new-timeout-id')
    controller = _controller_for_start_query(unit='cached', _delay_id='old-timeout-id')
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=SimpleNamespace(connect=lambda *a: 'sig')))

    controller.start_query()

    assert removed == ['old-timeout-id']
    assert controller._delay_id == 'new-timeout-id'


def test_start_query_schedules_send_tm_query_after_the_delay(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.timeout_add', lambda delay, cb: scheduled.append(cb) or 'id')
    controller = _controller_for_start_query(unit='cached')
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=SimpleNamespace(connect=lambda *a: 'sig')))
    sent = []
    controller.send_tm_query = lambda: sent.append(True)

    controller.start_query()
    result = scheduled[0]()  # invoke the deferred start_query() closure

    assert sent == [True]
    assert controller._delay_id is None
    assert result is False


# _on_cursor_changed() #

def test_on_cursor_changed_clears_storecursor_and_returns_when_none():
    controller = _bare_controller()
    controller.start_query = lambda: pytest.fail('must not query without a cursor')

    result = controller._on_cursor_changed(None)

    assert controller.storecursor is None
    assert result is None


def test_on_cursor_changed_returns_when_the_dereffed_unit_is_none():
    cursor = SimpleNamespace(deref=lambda: None)
    controller = _bare_controller()
    controller.start_query = lambda: pytest.fail('must not query without a unit')

    controller._on_cursor_changed(cursor)

    assert controller.unit is None


def _suggestions_controller(unit, active=True, summoned=False, isvisible=False):
    events = []
    controller = _bare_controller(unit=unit, _delay_id=None, storecursor=object())
    controller.start_query = lambda: events.append('query')
    controller.view = SimpleNamespace(
        active=active, summoned=summoned, isvisible=isvisible,
        hide=lambda: events.append('hide'),
        mnu_suggestions=SimpleNamespace(set_active=lambda v: pytest.fail('must not change the toggle')),
    )
    return controller, events


@pytest.mark.parametrize('translated, active, expected', [
    (False, True, ['query']),
    (True, True, ['hide']),   # translated units only get suggestions on request
    (False, False, ['hide']),
    (True, False, ['hide']),
])
def test_on_cursor_changed_never_changes_the_toggle(translated, active, expected):
    unit = SimpleNamespace(istranslated=lambda: translated)
    controller, events = _suggestions_controller(unit, active=active, summoned=True)

    controller._on_cursor_changed(SimpleNamespace(deref=lambda: unit))

    assert events == expected
    assert controller.view.summoned is False


@pytest.mark.parametrize('active', [True, False])
def test_summon_queries_a_translated_unit_whether_or_not_suggestions_are_on(active):
    unit = SimpleNamespace(istranslated=lambda: True)
    controller, events = _suggestions_controller(None, active=active)
    controller.storecursor = SimpleNamespace(deref=lambda: unit)

    controller.summon()

    assert controller.unit is unit
    assert controller.view.summoned is True
    assert events == ['query']


def test_summon_with_suggestions_already_shown_does_not_requery():
    unit = SimpleNamespace(istranslated=lambda: False)
    controller, events = _suggestions_controller(None, isvisible=True)
    controller.storecursor = SimpleNamespace(deref=lambda: unit)

    controller.summon()

    assert events == []


def test_summon_without_a_file_does_nothing():
    controller, events = _suggestions_controller(None)
    controller.storecursor = None

    controller.summon()

    assert events == []


# _on_mode_selected() / _on_target_focused() #

@pytest.mark.parametrize('translated, active, summoned, queries', [
    (False, True, False, [True]),
    (True, True, False, []),    # translated units don't show suggestions by themselves
    (False, False, False, []),
    (True, False, True, [True]),  # asked for with F9
])
def test_a_context_change_queries_again_where_suggestions_apply(translated, active, summoned, queries):
    unit = SimpleNamespace(istranslated=lambda: translated)
    calls = []
    controller = _bare_controller(storecursor=SimpleNamespace(deref=lambda: unit))
    controller.view = SimpleNamespace(active=active, summoned=summoned)
    controller.start_query = lambda: calls.append(True)

    controller._on_context_selected(None, 1)

    assert calls == queries


def test_a_context_change_without_a_file_does_nothing():
    controller = _bare_controller(storecursor=None)
    controller.start_query = lambda: pytest.fail('must not query')

    controller._on_context_selected(None, 1)


def test_on_mode_selected_updates_the_view_geometry():
    controller = _bare_controller()
    calls = []
    controller.view = SimpleNamespace(update_geometry=lambda: calls.append(True))

    controller._on_mode_selected(None, None)

    assert calls == [True]


def test_completion_popup_toggled_suspends_and_resumes_the_view():
    # The TM window and the completion list would otherwise overlap.
    controller = _bare_controller()
    calls = []
    controller.view = SimpleNamespace(suspend=lambda: calls.append('suspend'), resume=lambda: calls.append('resume'))

    controller._on_completion_popup_toggled(None, True)
    controller._on_completion_popup_toggled(None, False)

    assert calls == ['suspend', 'resume']


def test_on_target_focused_updates_the_view_geometry():
    controller = _bare_controller()
    calls = []
    controller.view = SimpleNamespace(update_geometry=lambda: calls.append(True))

    controller._on_target_focused(None, 0)

    assert calls == [True]


# _on_store_closed() #

def test_on_store_closed_disconnects_the_cursor_and_hides_the_view():
    controller = _bare_controller()
    disconnected = []
    controller.storecursor = SimpleNamespace(disconnect=disconnected.append)
    controller._cursor_changed_id = 'sig-id'
    calls = []
    controller.view = SimpleNamespace(hide=lambda: calls.append('hide'))

    controller._on_store_closed(None)

    assert disconnected == ['sig-id']
    assert controller.storecursor is None
    assert controller._cursor_changed_id == 0
    assert calls == ['hide']


def test_on_store_closed_is_safe_without_a_prior_cursor_subscription():
    controller = _bare_controller()
    controller.view = SimpleNamespace(hide=lambda: None)

    controller._on_store_closed(None)  # must not raise

    assert controller.storecursor is None


# _on_store_loaded() #

def test_on_store_loaded_connects_the_new_cursor_and_schedules_the_first_unit(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.idle_add', idle_calls.append)
    new_cursor = SimpleNamespace(connect=lambda signal, handler: 'new-sig')
    controller = _bare_controller()

    controller._on_store_loaded(SimpleNamespace(cursor=new_cursor))

    assert controller.storecursor is new_cursor
    assert controller._cursor_changed_id == 'new-sig'
    assert len(idle_calls) == 1


def test_on_store_loaded_disconnects_the_previous_cursor_first(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.idle_add', lambda f: None)
    disconnected = []
    old_cursor = SimpleNamespace(disconnect=disconnected.append)
    new_cursor = SimpleNamespace(connect=lambda signal, handler: 'new-sig')
    controller = _bare_controller(storecursor=old_cursor, _cursor_changed_id='old-sig')

    controller._on_store_loaded(SimpleNamespace(cursor=new_cursor))

    assert disconnected == ['old-sig']


def test_on_store_loaded_handles_the_first_unit_via_the_idle_callback(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('virtaal.plugins.tm.tmcontroller.GLib.idle_add', idle_calls.append)
    new_cursor = SimpleNamespace(connect=lambda signal, handler: 'new-sig')
    controller = _bare_controller()
    seen = []
    controller._on_cursor_changed = lambda cursor: seen.append(cursor)

    controller._on_store_loaded(SimpleNamespace(cursor=new_cursor))
    result = idle_calls[0]()

    assert seen == [new_cursor]
    assert result is False


def test_update_suggestions_before_a_file_is_open_does_nothing():
    # TMView's constructor ticks the toggle before TMController has a view.
    controller = _bare_controller(storecursor=None)

    controller.update_suggestions()  # must not raise
