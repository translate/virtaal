#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import GObject, Gtk

from virtaal.views.widgets.storetreemodel import StoreTreeModel


class _FakeUnit:
    def __init__(self, notes='', locations=None):
        self._notes = notes
        self._locations = locations or []

    def getnotes(self):
        return self._notes

    def getlocations(self):
        return self._locations


def _model(units):
    return StoreTreeModel(list(units))


# do_get_flags() / do_get_n_columns() / do_get_column_type() #

def test_get_flags_is_a_flat_persistent_list():
    model = _model([])

    assert model.get_flags() == Gtk.TreeModelFlags.ITERS_PERSIST | Gtk.TreeModelFlags.LIST_ONLY


def test_get_n_columns_is_three():
    assert _model([]).get_n_columns() == 3


def test_get_column_type_matches_each_columns_real_type():
    model = _model([])

    assert model.get_column_type(0) == GObject.TYPE_STRING
    assert model.get_column_type(1) == GObject.TYPE_PYOBJECT
    assert model.get_column_type(2) == GObject.TYPE_BOOLEAN


# do_get_iter() / do_get_path() #

def test_get_iter_succeeds_for_an_in_range_path():
    model = _model([_FakeUnit(), _FakeUnit()])

    it = model.get_iter(Gtk.TreePath((1,)))

    assert it.user_data == 1


def test_get_iter_fails_for_an_out_of_range_path():
    model = _model([_FakeUnit()])

    with pytest.raises(ValueError):
        model.get_iter(Gtk.TreePath((1,)))


def test_get_path_round_trips_an_iters_row_index():
    model = _model([_FakeUnit(), _FakeUnit(), _FakeUnit()])

    it = model.get_iter(Gtk.TreePath((2,)))

    assert model.get_path(it).get_indices() == [2]


# do_get_value() #

def test_get_value_column_0_returns_the_units_own_note():
    model = _model([_FakeUnit(notes='a translator note')])

    it = model.get_iter(Gtk.TreePath((0,)))

    assert model.get_value(it, 0) == 'a translator note'


def test_get_value_column_0_falls_back_to_the_first_location_without_a_note():
    model = _model([_FakeUnit(locations=['file.py:12', 'file.py:34'])])

    it = model.get_iter(Gtk.TreePath((0,)))

    assert model.get_value(it, 0) == 'file.py:12'


def test_get_value_column_0_is_an_empty_string_without_a_note_or_a_location():
    # Must be a real str, not None - a bare None return for a
    # TYPE_STRING column marshals as an untyped GValue, which a real
    # Gtk.TreeView's cell renderer silently rejects with a
    # g_value_type_compatible warning on every such row.
    model = _model([_FakeUnit()])

    it = model.get_iter(Gtk.TreePath((0,)))

    assert model.get_value(it, 0) == ''


def test_get_value_column_1_returns_the_unit_itself():
    unit = _FakeUnit()
    model = _model([unit])

    it = model.get_iter(Gtk.TreePath((0,)))

    assert model.get_value(it, 1) is unit


def test_get_value_column_2_reflects_the_currently_editable_row():
    model = _model([_FakeUnit(), _FakeUnit()])
    model._current_editable = 1

    assert model.get_value(model.get_iter(Gtk.TreePath((0,))), 2) is False
    assert model.get_value(model.get_iter(Gtk.TreePath((1,))), 2) is True


# do_iter_next() #

def test_iter_next_advances_to_the_next_row():
    model = _model([_FakeUnit(), _FakeUnit()])

    it = model.iter_next(model.get_iter(Gtk.TreePath((0,))))

    assert it.user_data == 1


def test_iter_next_returns_none_past_the_last_row():
    model = _model([_FakeUnit()])

    assert model.iter_next(model.get_iter(Gtk.TreePath((0,)))) is None


# do_iter_children() / do_iter_has_child() / do_iter_n_children() / do_iter_nth_child() #

def test_iter_children_of_the_root_is_the_first_row():
    model = _model([_FakeUnit(), _FakeUnit()])

    it = model.iter_children(None)

    assert it.user_data == 0


def test_iter_children_of_the_root_is_none_when_empty():
    assert _model([]).iter_children(None) is None


def test_iter_has_child_is_always_false():
    model = _model([_FakeUnit()])

    assert model.iter_has_child(model.get_iter(Gtk.TreePath((0,)))) is False


def test_iter_n_children_of_the_root_is_the_row_count():
    assert _model([_FakeUnit(), _FakeUnit(), _FakeUnit()]).iter_n_children(None) == 3


def test_iter_n_children_of_a_row_is_zero():
    model = _model([_FakeUnit()])

    assert model.iter_n_children(model.get_iter(Gtk.TreePath((0,)))) == 0


def test_iter_nth_child_of_the_root_returns_that_row():
    model = _model([_FakeUnit(), _FakeUnit(), _FakeUnit()])

    it = model.iter_nth_child(None, 2)

    assert it.user_data == 2


def test_iter_nth_child_of_the_root_is_none_out_of_range():
    assert _model([_FakeUnit()]).iter_nth_child(None, 99) is None


# do_iter_parent() #

def test_iter_parent_is_always_none():
    model = _model([_FakeUnit()])

    assert model.iter_parent(model.get_iter(Gtk.TreePath((0,)))) is None


# set_editable() #

def test_set_editable_moves_the_editable_flag_and_notifies_both_rows():
    model = _model([_FakeUnit(), _FakeUnit(), _FakeUnit()])
    model._current_editable = 0
    changed = []
    model.connect('row-changed', lambda m, path, it: changed.append(path.get_indices()[0]))

    model.set_editable((2,))

    assert model._current_editable == 2
    assert changed == [0, 2]


# store_index_to_path() / path_to_store_index() #

def test_store_index_to_path_wraps_the_index_in_a_tuple():
    assert _model([]).store_index_to_path(5) == (5,)


def test_path_to_store_index_returns_the_first_element():
    assert _model([]).path_to_store_index((3,)) == 3


def test_path_to_store_index_defaults_to_zero_without_a_path():
    assert _model([]).path_to_store_index(None) == 0
