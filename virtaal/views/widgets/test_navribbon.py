#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk
from translate.storage.workflow import StateEnum

from virtaal.views.widgets.navribbon import CHECK_FAILURE, NavRibbon


class FakeUnit:
    def __init__(self, state):
        self._state = state

    def get_state_n(self):
        return self._state


class FakeStore:
    def __init__(self, units):
        self._units = units

    def get_units(self):
        return self._units


class FakeStoreController:
    def __init__(self, stats=None, checks=None, cursor=None, store=None,
                 raise_no_store=False, raise_attribute_error=False,
                 raise_checks_not_ready=False):
        self._stats = stats
        self._checks = checks
        self.cursor = cursor
        self._store = store
        self._raise_no_store = raise_no_store
        self._raise_attribute_error = raise_attribute_error
        self._raise_checks_not_ready = raise_checks_not_ready

    def get_store_stats(self):
        if self._raise_attribute_error:
            raise AttributeError("'StoreController' object has no attribute 'store'")
        if self._raise_no_store:
            raise ValueError('No store to get checker from')
        return self._stats

    def get_store(self):
        if self._raise_attribute_error:
            raise AttributeError("'StoreController' object has no attribute 'store'")
        if self._raise_no_store:
            raise ValueError('No store to get checker from')
        return self._store

    def get_store_checks(self):
        if self._raise_attribute_error or self._raise_checks_not_ready:
            raise AttributeError("'StoreModel' object has no attribute 'checks'")
        if self._raise_no_store:
            raise ValueError('No store to get checker from')
        return self._checks

    def connect(self, *_args, **_kwargs):
        return 0

    def disconnect(self, *_args, **_kwargs):
        pass


class FakeMainController:
    def __init__(self, store_controller):
        self.store_controller = store_controller

    def connect(self, *_args, **_kwargs):
        return 0


class FakeUnitController:
    def __init__(self):
        self._next_id = 0
        self.disconnected = []

    def connect(self, _signal, _handler):
        self._next_id += 1
        return self._next_id

    def disconnect(self, handler_id):
        self.disconnected.append(handler_id)


class FakeCursor:
    def __init__(self):
        self.forced = []

    def force_index(self, index):
        self.forced.append(index)


def make_ribbon(stats=None, checks=None, cursor=None, units=None, raise_no_store=False,
                 raise_attribute_error=False, raise_checks_not_ready=False):
    store_controller = FakeStoreController(
        stats, checks, cursor, FakeStore(units or []),
        raise_no_store, raise_attribute_error, raise_checks_not_ready)
    main_controller = FakeMainController(store_controller)
    scrolled_window = Gtk.ScrolledWindow()
    ribbon = NavRibbon(main_controller, scrolled_window)
    return ribbon, store_controller, main_controller


def test_refresh_marks_reads_live_unit_state():
    stats = {'total': [0, 1, 2, 3]}
    units = [
        FakeUnit(StateEnum.EMPTY),
        FakeUnit(StateEnum.NEEDS_WORK),
        FakeUnit(StateEnum.FINAL),
        FakeUnit(StateEnum.UNREVIEWED),
    ]
    ribbon, _, _ = make_ribbon(stats, {}, units=units)

    assert ribbon._marks == [
        (0, 0, StateEnum.EMPTY),
        (0, 1, StateEnum.NEEDS_WORK),
        (0, 2, StateEnum.FINAL),
        (0, 3, StateEnum.UNREVIEWED),
    ]


def test_refresh_marks_check_failure_overrides_workflow_state():
    # A unit can be translated (even FINAL) *and* fail a quality check -
    # the check failure must win the mark's colour.
    stats = {'total': [0, 1]}
    units = [FakeUnit(StateEnum.FINAL), FakeUnit(StateEnum.FINAL)]
    checks = {'check-foo': [1]}
    ribbon, _, _ = make_ribbon(stats, checks, units=units)

    assert ribbon._marks == [
        (0, 0, StateEnum.FINAL),
        (0, 1, CHECK_FAILURE),
    ]


def test_refresh_marks_no_store_leaves_marks_empty():
    ribbon, _, _ = make_ribbon(raise_no_store=True)
    assert ribbon._marks == []


def test_refresh_marks_handles_store_controller_mid_construction():
    # 'controller-registered' fires from inside StoreController.__init__(),
    # synchronously, before that constructor reaches its own
    # "self.store = None" - get_store_stats()/get_store_checks() raise
    # AttributeError rather than the usual ValueError in that window.
    ribbon, _, _ = make_ribbon(raise_attribute_error=True)
    assert ribbon._marks == []


def test_refresh_marks_shows_stats_before_checks_are_computed():
    # store.checks isn't computed until QualityCheckMode first runs (mode
    # selection or a save) - a fresh file load must still show
    # untranslated/fuzzy/translated marks meanwhile, not go blank.
    stats = {'total': [0, 1]}
    units = [FakeUnit(StateEnum.EMPTY), FakeUnit(StateEnum.UNREVIEWED)]
    ribbon, _, _ = make_ribbon(stats, units=units, raise_checks_not_ready=True)

    assert ribbon._marks == [
        (0, 0, StateEnum.EMPTY),
        (0, 1, StateEnum.UNREVIEWED),
    ]


def test_on_unit_done_refreshes_the_just_edited_units_mark():
    # A unit's fuzzy/translated/workflow state only needs to wait for
    # 'unit-done' (leaving the unit), not a full file save.
    stats = {'total': [0, 1]}
    units = [FakeUnit(StateEnum.EMPTY), FakeUnit(StateEnum.UNREVIEWED)]
    ribbon, _, _ = make_ribbon(stats, {}, units=units)
    assert ribbon._marks[0] == (0, 0, StateEnum.EMPTY)

    units[0]._state = StateEnum.UNREVIEWED  # translator just typed a target
    ribbon._on_unit_done(None, units[0], True)

    assert ribbon._marks[0] == (0, 0, StateEnum.UNREVIEWED)


def test_on_unit_done_noop_when_not_modified():
    stats = {'total': [0]}
    units = [FakeUnit(StateEnum.EMPTY)]
    ribbon, _, _ = make_ribbon(stats, {}, units=units)

    units[0]._state = StateEnum.UNREVIEWED
    ribbon._on_unit_done(None, units[0], False)

    # _refresh_marks() wasn't re-run, so the stale EMPTY mark is unchanged.
    assert ribbon._marks[0] == (0, 0, StateEnum.EMPTY)


def test_maybe_bind_unit_controller_binds_once_available():
    stats = {'total': [0]}
    units = [FakeUnit(StateEnum.EMPTY)]
    ribbon, store_controller, main_controller = make_ribbon(stats, {}, units=units)
    assert ribbon._bound_unit_controller is None

    unit_controller = FakeUnitController()
    main_controller.unit_controller = unit_controller
    ribbon._maybe_bind_unit_controller()

    assert ribbon._bound_unit_controller is unit_controller

    # A second call with the same controller must not double-bind.
    ribbon._maybe_bind_unit_controller()
    assert unit_controller.disconnected == []


def test_unit_index_at_y_maps_fraction_of_height_to_unit_index():
    stats = {'total': list(range(10))}
    units = [FakeUnit(StateEnum.UNREVIEWED) for _ in range(10)]
    ribbon, _, _ = make_ribbon(stats, {}, units=units)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    assert ribbon._unit_index_at_y(0) == 0
    assert ribbon._unit_index_at_y(50) == 5
    # Clamped to the last unit, not out of range, at/after the bottom edge.
    assert ribbon._unit_index_at_y(100) == 9
    assert ribbon._unit_index_at_y(999) == 9


def test_unit_index_at_y_no_marks_returns_none():
    ribbon, _, _ = make_ribbon(raise_no_store=True)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    assert ribbon._unit_index_at_y(50) is None


def test_jump_to_y_forces_cursor_to_exact_clicked_unit():
    # force_index(), not cursor.index/select_unit(): a click must land
    # on the exact unit even if a mode has narrowed cursor.indices to a
    # filtered subset.
    cursor = FakeCursor()
    stats = {'total': list(range(10))}
    units = [FakeUnit(StateEnum.UNREVIEWED) for _ in range(10)]
    ribbon, _, _ = make_ribbon(stats, {}, cursor=cursor, units=units)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(35)

    assert cursor.forced == [3]


def test_jump_to_y_noop_without_marks():
    cursor = FakeCursor()
    ribbon, _, _ = make_ribbon(raise_no_store=True, cursor=cursor)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(50)

    assert cursor.forced == []


def test_jump_to_y_noop_without_cursor():
    stats = {'total': list(range(10))}
    units = [FakeUnit(StateEnum.UNREVIEWED) for _ in range(10)]
    ribbon, store_controller, _ = make_ribbon(stats, {}, cursor=None, units=units)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(50)  # must not raise despite cursor being None
