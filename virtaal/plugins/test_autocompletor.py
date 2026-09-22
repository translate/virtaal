#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.plugins.autocompletor import AutoCompletor


def _ac(comp_len=AutoCompletor.DEFAULT_COMPLETION_LENGTH):
    return AutoCompletor(main_controller=None, comp_len=comp_len)


# isusable() #

def test_isusable_rejects_a_word_at_the_length_boundary():
    ac = _ac(comp_len=4)
    assert ac.isusable('123456') is False  # len 6 == comp_len + 2


def test_isusable_accepts_a_word_just_over_the_boundary():
    ac = _ac(comp_len=4)
    assert ac.isusable('1234567') is True  # len 7 > comp_len + 2


# add_words() / _update_word_list() #

def test_add_words_filters_out_words_too_short_to_be_usable():
    ac = _ac(comp_len=4)
    ac.add_words(['short', 'alongenoughword'])

    assert 'short' not in ac._word_list
    assert 'alongenoughword' in ac._word_list


def test_add_words_orders_the_word_list_by_frequency_descending():
    ac = _ac(comp_len=1)
    ac.add_words(['rare', 'common', 'common', 'common', 'medium', 'medium'])

    assert ac._word_list == ['common', 'medium', 'rare']


def test_add_words_with_update_false_defers_rebuilding_the_word_list():
    ac = _ac(comp_len=1)
    ac.add_words(['alongword'], update=False)

    assert 'alongword' in ac._word_freq
    assert ac._word_list == []


def test_add_words_accumulates_frequency_across_calls():
    ac = _ac(comp_len=1)
    ac.add_words(['word'])
    ac.add_words(['word'])

    assert ac._word_freq['word'] == 2


# add_words_from_units() #

def test_add_words_from_units_splits_target_text_into_words():
    ac = _ac(comp_len=1)
    unit = SimpleNamespace(target='hello world')

    ac.add_words_from_units([unit])

    assert 'hello' in ac._word_list
    assert 'world' in ac._word_list


def test_add_words_from_units_skips_a_unit_with_no_target():
    ac = _ac(comp_len=1)
    unit = SimpleNamespace(target='')

    ac.add_words_from_units([unit])  # must not raise

    assert ac._word_list == []


# autocomplete() #

def test_autocomplete_finds_the_first_matching_prefix_by_frequency():
    ac = _ac(comp_len=1)
    ac.add_words(['helsinki', 'helsinki', 'hello'])  # helsinki more frequent

    word, suffix = ac.autocomplete('hel')

    assert word == 'helsinki'
    assert suffix == 'sinki'


def test_autocomplete_returns_none_and_empty_suffix_for_no_match():
    ac = _ac(comp_len=1)
    ac.add_words(['hello'])

    word, suffix = ac.autocomplete('xyz')

    assert word is None
    assert suffix == ''


# clear_words() #

def test_clear_words_resets_frequency_and_list():
    ac = _ac(comp_len=1)
    ac.add_words(['hello'])

    ac.clear_words()

    assert ac._word_list == []
    assert ac._word_freq['hello'] == 0


# remove_words() - normal (in-sync) case; the desync/exception case
# fixed in #3637 is covered separately below.

def test_remove_words_removes_a_word_present_in_both_structures():
    ac = _ac(comp_len=1)
    ac.add_words(['hello', 'world'])

    ac.remove_words('hello')

    assert 'hello' not in ac._word_list
    assert 'world' in ac._word_list


def test_remove_words_accepts_a_list_of_words():
    ac = _ac(comp_len=1)
    ac.add_words(['hello', 'world', 'kept'])

    ac.remove_words(['hello', 'world'])

    assert ac._word_list == ['kept']


def test_remove_words_tolerates_a_word_freq_entry_never_synced_to_word_list():
    """add_words(update=False) - used internally by add_words_from_units()'s
        per-unit loop - populates _word_freq without rebuilding _word_list,
        so the two can legitimately disagree about a given word. Removing
        such a word used to raise an uncaught ValueError from
        _word_list.remove() (only KeyError was ever caught)."""
    ac = _ac(comp_len=1)
    ac.add_words(['itisalongword'], update=False)
    assert 'itisalongword' in ac._word_freq
    assert 'itisalongword' not in ac._word_list

    ac.remove_words('itisalongword')  # must not raise

    assert 'itisalongword' not in ac._word_freq


def test_remove_words_tolerates_the_same_desync_for_a_list_of_words():
    ac = _ac(comp_len=1)
    ac.add_words(['itisalongword'], update=False)

    ac.remove_words(['itisalongword', 'nosuchword'])  # must not raise
