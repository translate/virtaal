#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import shutil

import pytest
from translate.storage import factory

from virtaal.support.tutorial import create_localized_tutorial


@pytest.fixture
def tutorial_store():
    """A real tutorial file, saved to a fresh temp directory and parsed
    back with the same translate-toolkit factory a real Open would use -
    create_localized_tutorial() makes its own tempfile.mkdtemp(), which
    doesn't clean itself up."""
    filename = create_localized_tutorial()
    try:
        yield factory.getobject(filename)
    finally:
        shutil.rmtree(os.path.dirname(filename))


def test_creates_a_real_pot_file_on_disk():
    filename = create_localized_tutorial()
    try:
        assert os.path.isfile(filename)
        assert filename.endswith('.pot')
    finally:
        shutil.rmtree(os.path.dirname(filename))


def test_each_call_gets_its_own_fresh_temp_directory():
    first = create_localized_tutorial()
    second = create_localized_tutorial()
    try:
        assert os.path.dirname(first) != os.path.dirname(second)
    finally:
        shutil.rmtree(os.path.dirname(first))
        shutil.rmtree(os.path.dirname(second))


def test_a_plain_entry_gets_its_developer_note(tutorial_store):
    [unit] = [u for u in tutorial_store.units if u.source == 'Welcome']

    assert 'Welcome to the Virtaal tutorial' in str(unit.getnotes('developer'))


def test_a_plural_entry_is_added_with_an_empty_target_for_each_form(tutorial_store):
    [unit] = [u for u in tutorial_store.units if u.hasplural()]

    assert unit.target == ['', '']


def test_entries_sharing_a_source_are_distinguished_by_context(tutorial_store):
    view_units = [u for u in tutorial_store.units if u.source == 'View']

    assert {u.getcontext() for u in view_units} == {'verb', 'noun'}


def test_every_entry_has_a_source_and_a_developer_note(tutorial_store):
    entries = [u for u in tutorial_store.units if not u.isheader()]

    assert len(entries) > 30  # every real entry, not just a couple
    for unit in entries:
        assert unit.source
        assert str(unit.getnotes('developer')).strip()
