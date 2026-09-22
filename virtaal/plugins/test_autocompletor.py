#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.plugins.autocompletor import AutoCompletor


def test_remove_words_tolerates_a_word_freq_entry_never_synced_to_word_list():
    """add_words(update=False) - used internally by add_words_from_units()'s
        per-unit loop - populates _word_freq without rebuilding _word_list,
        so the two can legitimately disagree about a given word. Removing
        such a word used to raise an uncaught ValueError from
        _word_list.remove() (only KeyError was ever caught)."""
    ac = AutoCompletor(main_controller=None)
    ac.add_words(['itisalongword'], update=False)
    assert 'itisalongword' in ac._word_freq
    assert 'itisalongword' not in ac._word_list

    ac.remove_words('itisalongword')  # must not raise

    assert 'itisalongword' not in ac._word_freq


def test_remove_words_tolerates_the_same_desync_for_a_list_of_words():
    ac = AutoCompletor(main_controller=None)
    ac.add_words(['itisalongword'], update=False)

    ac.remove_words(['itisalongword', 'nosuchword'])  # must not raise
