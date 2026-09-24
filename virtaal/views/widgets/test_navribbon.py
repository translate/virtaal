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


class FakeStoreController:
    def __init__(self, stats=None, checks=None, cursor=None, raise_no_store=False,
                 raise_attribute_error=False, raise_checks_not_ready=False):
        self._stats = stats
        self._checks = checks
        self.cursor = cursor
        self._raise_no_store = raise_no_store
        self._raise_attribute_error = raise_attribute_error
        self._raise_checks_not_ready = raise_checks_not_ready

    def get_store_stats(self):
        if self._raise_attribute_error:
            raise AttributeError("'StoreController' object has no attribute 'store'")
        if self._raise_no_store:
            raise ValueError('No store to get checker from')
        return self._stats

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


class FakeCursor:
    def __init__(self):
        self.forced = []

    def force_index(self, index):
        self.forced.append(index)


def make_ribbon(stats=None, checks=None, cursor=None, raise_no_store=False,
                 raise_attribute_error=False, raise_checks_not_ready=False):
    store_controller = FakeStoreController(
        stats, checks, cursor, raise_no_store, raise_attribute_error, raise_checks_not_ready)
    main_controller = FakeMainController(store_controller)
    scrolled_window = Gtk.ScrolledWindow()
    ribbon = NavRibbon(main_controller, scrolled_window)
    return ribbon, store_controller


def test_refresh_marks_uses_extended_workflow_state():
    stats = {
        'total': [0, 1, 2, 3],
        'extended': {
            StateEnum.EMPTY: [0],
            StateEnum.NEEDS_WORK: [1],
            StateEnum.FINAL: [2],
            StateEnum.UNREVIEWED: [3],
        },
    }
    ribbon, _ = make_ribbon(stats, {})

    assert ribbon._marks == [
        (0, 0, StateEnum.EMPTY),
        (0, 1, StateEnum.NEEDS_WORK),
        (0, 2, StateEnum.FINAL),
        (0, 3, StateEnum.UNREVIEWED),
    ]


def test_refresh_marks_missing_extended_state_defaults_to_unreviewed():
    # A unit index with no entry in stats['extended'] at all (shouldn't
    # normally happen once a store is loaded, but the ribbon must not
    # crash on it) falls back to the "translated, unreviewed" tier.
    stats = {'total': [5], 'extended': {}}
    ribbon, _ = make_ribbon(stats, {})

    assert ribbon._marks == [(0, 5, StateEnum.UNREVIEWED)]


def test_refresh_marks_check_failure_overrides_workflow_state():
    # A unit can be translated (even FINAL) *and* fail a quality check -
    # the check failure must win the mark's colour.
    stats = {
        'total': [0, 1],
        'extended': {StateEnum.FINAL: [0, 1]},
    }
    checks = {'check-foo': [1]}
    ribbon, _ = make_ribbon(stats, checks)

    assert ribbon._marks == [
        (0, 0, StateEnum.FINAL),
        (0, 1, CHECK_FAILURE),
    ]


def test_refresh_marks_no_store_leaves_marks_empty():
    ribbon, _ = make_ribbon(raise_no_store=True)
    assert ribbon._marks == []


def test_refresh_marks_handles_store_controller_mid_construction():
    # 'controller-registered' fires from inside StoreController.__init__(),
    # synchronously, before that constructor reaches its own
    # "self.store = None" - get_store_stats()/get_store_checks() raise
    # AttributeError rather than the usual ValueError in that window.
    ribbon, _ = make_ribbon(raise_attribute_error=True)
    assert ribbon._marks == []


def test_refresh_marks_shows_stats_before_checks_are_computed():
    # store.checks isn't computed until QualityCheckMode first runs (mode
    # selection or a save) - a fresh file load must still show
    # untranslated/fuzzy/translated marks meanwhile, not go blank.
    stats = {
        'total': [0, 1],
        'extended': {StateEnum.EMPTY: [0], StateEnum.UNREVIEWED: [1]},
    }
    ribbon, _ = make_ribbon(stats, raise_checks_not_ready=True)

    assert ribbon._marks == [
        (0, 0, StateEnum.EMPTY),
        (0, 1, StateEnum.UNREVIEWED),
    ]


def test_unit_index_at_y_maps_fraction_of_height_to_unit_index():
    stats = {'total': list(range(10)), 'extended': {}}
    ribbon, _ = make_ribbon(stats, {})
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    assert ribbon._unit_index_at_y(0) == 0
    assert ribbon._unit_index_at_y(50) == 5
    # Clamped to the last unit, not out of range, at/after the bottom edge.
    assert ribbon._unit_index_at_y(100) == 9
    assert ribbon._unit_index_at_y(999) == 9


def test_unit_index_at_y_no_marks_returns_none():
    ribbon, _ = make_ribbon(raise_no_store=True)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    assert ribbon._unit_index_at_y(50) is None


def test_jump_to_y_forces_cursor_to_exact_clicked_unit():
    # force_index(), not cursor.index/select_unit(): a click must land
    # on the exact unit even if a mode has narrowed cursor.indices to a
    # filtered subset.
    cursor = FakeCursor()
    stats = {'total': list(range(10)), 'extended': {}}
    ribbon, _ = make_ribbon(stats, {}, cursor=cursor)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(35)

    assert cursor.forced == [3]


def test_jump_to_y_noop_without_marks():
    cursor = FakeCursor()
    ribbon, _ = make_ribbon(raise_no_store=True, cursor=cursor)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(50)

    assert cursor.forced == []


def test_jump_to_y_noop_without_cursor():
    stats = {'total': list(range(10)), 'extended': {}}
    ribbon, store_controller = make_ribbon(stats, {}, cursor=None)
    ribbon.get_allocation = lambda: SimpleNamespace(height=100)

    ribbon._jump_to_y(50)  # must not raise despite cursor being None
