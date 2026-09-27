#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.set_enumerator import UnionSetEnumerator
from virtaal.support.sorted_set import SortedSet


def test_init_with_no_sets_starts_empty():
    u = UnionSetEnumerator()

    assert len(u) == 0
    assert u.set.data == []


def test_init_with_one_set_is_just_that_set():
    u = UnionSetEnumerator(SortedSet([1, 2, 3]))

    assert list(u.set) == [1, 2, 3]


def test_init_unions_several_overlapping_sets():
    u = UnionSetEnumerator(SortedSet([1, 2, 3]), SortedSet([2, 3, 4]), SortedSet([5]))

    assert list(u.set) == [1, 2, 3, 4, 5]


def test_len_reflects_the_union():
    assert len(UnionSetEnumerator(SortedSet([1, 2]), SortedSet([2, 3]))) == 3


def test_contains():
    u = UnionSetEnumerator(SortedSet([1, 2]), SortedSet([2, 3]))

    assert 2 in u
    assert 99 not in u


def test_before_add_adds_a_new_element_and_emits_add_with_its_union_position():
    u = UnionSetEnumerator(SortedSet([1, 3]))
    added = []
    u.connect('add', lambda _u, pos, elem: added.append((pos, elem)))

    u._before_add(None, 0, 2)

    assert list(u.set) == [1, 2, 3]
    assert added == [(1, 2)]


def test_before_add_ignores_an_element_already_in_the_union():
    u = UnionSetEnumerator(SortedSet([1, 2, 3]))
    added = []
    u.connect('add', lambda *a: added.append(a))

    u._before_add(None, 0, 2)

    assert list(u.set) == [1, 2, 3]
    assert added == []


def test_before_remove_removes_an_element_and_emits_remove_with_its_former_position():
    u = UnionSetEnumerator(SortedSet([1, 2, 3]))
    removed = []
    u.connect('remove', lambda _u, pos, elem: removed.append((pos, elem)))

    u._before_remove(None, 0, 2)

    assert list(u.set) == [1, 3]
    assert removed == [(1, 2)]


def test_before_remove_ignores_an_element_not_in_the_union():
    u = UnionSetEnumerator(SortedSet([1, 2, 3]))
    removed = []
    u.connect('remove', lambda *a: removed.append(a))

    u._before_remove(None, 0, 99)

    assert list(u.set) == [1, 2, 3]
    assert removed == []


def test_remove_removes_the_element_from_every_underlying_set():
    a = SortedSet([1, 2])
    b = SortedSet([2, 3])
    u = UnionSetEnumerator(a, b)

    u.remove(2)

    assert a.data == [1]
    assert b.data == [3]
