#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.sorted_set import SortedSet


def test_init_sorts_and_dedupes():
    s = SortedSet([3, 1, 2, 2, 1])

    assert s.data == [1, 2, 3]


def test_init_on_an_empty_iterable():
    s = SortedSet([])

    assert s.data == []


def test_repr():
    assert repr(SortedSet([2, 1])) == 'SortedSet([1, 2])'


def test_iter_yields_in_sorted_order():
    assert list(SortedSet([3, 1, 2])) == [1, 2, 3]


def test_contains():
    s = SortedSet([1, 3, 5])

    assert 3 in s
    assert 4 not in s
    assert 6 not in s  # past the end of the data


def test_add_inserts_in_sorted_position_and_emits_signals():
    s = SortedSet([1, 3])
    before, after = [], []
    s.connect('before-add', lambda _s, i, e: before.append((i, e)))
    s.connect('added', lambda _s, i, e: after.append((i, e)))

    s.add(2)

    assert s.data == [1, 2, 3]
    assert before == [(1, 2)]
    assert after == [(1, 2)]


def test_add_is_a_noop_for_an_existing_element():
    s = SortedSet([1, 2, 3])
    calls = []
    s.connect('added', lambda *a: calls.append(a))

    s.add(2)

    assert s.data == [1, 2, 3]
    assert calls == []


def test_remove_deletes_and_emits_signals():
    s = SortedSet([1, 2, 3])
    before, after = [], []
    s.connect('before-remove', lambda _s, i, e: before.append((i, e)))
    s.connect('removed', lambda _s, i, e: after.append((i, e)))

    s.remove(2)

    assert s.data == [1, 3]
    assert before == [(1, 2)]
    assert after == [(1, 2)]


def test_remove_is_a_noop_for_a_missing_element():
    s = SortedSet([1, 2, 3])
    calls = []
    s.connect('removed', lambda *a: calls.append(a))

    s.remove(99)

    assert s.data == [1, 2, 3]
    assert calls == []


def test_gt_compares_the_underlying_sorted_data():
    assert SortedSet([1, 2, 3]) > SortedSet([1, 2])
    assert not (SortedSet([1, 2]) > SortedSet([1, 2, 3]))


def test_gt_accepts_a_plain_iterable_as_the_other_operand():
    assert SortedSet([1, 2, 3]) > [1, 2]


def test_union_interleaves_two_overlapping_sets():
    a = SortedSet([1, 2, 3, 5])
    b = SortedSet([2, 3, 4])

    assert a.union(b).data == [1, 2, 3, 4, 5]


def test_union_accepts_a_plain_iterable_as_the_other_operand():
    assert SortedSet([1, 2, 3]).union([2, 3, 4]).data == [1, 2, 3, 4]


def test_union_with_an_empty_other_set():
    a = SortedSet([1, 2, 3])

    assert a.union(SortedSet([])).data == [1, 2, 3]
    assert SortedSet([]).union(a).data == [1, 2, 3]


def test_union_with_disjoint_sets():
    assert SortedSet([1, 2]).union(SortedSet([3, 4])).data == [1, 2, 3, 4]


def test_intersection_of_two_overlapping_sets():
    a = SortedSet([1, 2, 3, 5])
    b = SortedSet([2, 3, 4])

    assert a.intersection(b).data == [2, 3]


def test_intersection_with_an_empty_other_set():
    a = SortedSet([1, 2, 3])

    assert a.intersection(SortedSet([])).data == []
    assert SortedSet([]).intersection(a).data == []


def test_intersection_of_disjoint_sets():
    assert SortedSet([1, 2]).intersection(SortedSet([3, 4])).data == []


def test_difference_of_two_overlapping_sets():
    a = SortedSet([1, 2, 3, 5])
    b = SortedSet([2, 3, 4])

    assert a.difference(b).data == [1, 5]


def test_difference_with_an_empty_other_set():
    a = SortedSet([1, 2, 3])

    assert a.difference(SortedSet([])).data == [1, 2, 3]
    assert SortedSet([]).difference(a).data == []


def test_symmetric_difference_of_two_overlapping_sets():
    a = SortedSet([1, 2, 3, 5])
    b = SortedSet([2, 3, 4])

    assert a.symmetric_difference(b).data == [1, 4, 5]


def test_symmetric_difference_with_an_empty_other_set():
    a = SortedSet([1, 2, 3])

    assert a.symmetric_difference(SortedSet([])).data == [1, 2, 3]
    assert SortedSet([]).symmetric_difference(a).data == [1, 2, 3]


def test_symmetric_difference_of_disjoint_sets():
    assert SortedSet([1, 2]).symmetric_difference(SortedSet([3, 4])).data == [1, 2, 3, 4]
