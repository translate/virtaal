#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib

from translate.misc.multistring import multistring
from translate.storage import ts2

from virtaal.support import ts2_compat

# Written by Qt 6 lconvert, so it is laid out as lupdate and Linguist
# write it.
FIXTURE = 'devsupport/testfiles/lengthvariants.ts'


def _load():
    with open(FIXTURE, 'rb') as f:
        # A Windows checkout may have CRLF line endings.
        original = f.read().replace(b'\r\n', b'\n')
    return original, ts2.tsfile.parsestring(original)


def _unit(store, source):
    return next(u for u in store.units if str(u.source).startswith(source))


def test_untouched_file_round_trips_byte_identical():
    original, store = _load()
    for unit in store.units:
        unit.target  # noqa: B018 - reading must not change the file
    assert bytes(store) == original


def test_variants_target_reads_as_its_first_variant():
    _original, store = _load()
    unit = _unit(store, 'Save the current document')
    assert unit.target == 'Stoor die huidige lêer'
    assert unit.istranslated()


def test_unfinished_variants_message_reads_as_fuzzy():
    _original, store = _load()
    unit = _unit(store, 'Open')
    assert unit.target == 'Maak oop nou'
    assert unit.isfuzzy()


def test_plural_variants_read_as_each_forms_first_variant():
    _original, store = _load()
    unit = _unit(store, '%n files deleted')
    assert unit.target.strings == ['%n lêer geskrap', '%n lêers geskrap']


def test_setting_the_target_keeps_the_other_variants():
    original, store = _load()
    _unit(store, 'Save the current document').target = 'Stoor hierdie lêer'
    expected = original.replace(
        '<lengthvariant>Stoor die huidige lêer</lengthvariant>'.encode(),
        '<lengthvariant>Stoor hierdie lêer</lengthvariant>'.encode())
    assert bytes(store) == expected


def test_setting_the_target_keeps_the_type():
    original, store = _load()
    unit = _unit(store, 'Open')
    unit.target = 'Maak dit oop'
    assert unit.isfuzzy()
    unit.markfuzzy(False)
    expected = original.replace(
        b'<translation type="unfinished" variants="yes">\n'
        b'            <lengthvariant>Maak oop nou</lengthvariant>',
        b'<translation variants="yes">\n'
        b'            <lengthvariant>Maak dit oop</lengthvariant>')
    assert expected != original
    assert bytes(store) == expected


def test_setting_an_obsolete_target_keeps_it_obsolete():
    original, store = _load()
    unit = _unit(store, 'Old')
    unit.target = 'Ou'
    assert unit.isobsolete()
    assert bytes(store) == original.replace(
        b'<lengthvariant>Oud</lengthvariant>', b'<lengthvariant>Ou</lengthvariant>')


def test_setting_a_plural_target_keeps_each_forms_variants():
    original, store = _load()
    _unit(store, '%n files deleted').target = multistring(['%n lêer weg', '%n lêers weg'])
    expected = original.replace(
        b'<lengthvariant>%n l\xc3\xaaer geskrap</lengthvariant>',
        b'<lengthvariant>%n l\xc3\xaaer weg</lengthvariant>').replace(
        b'<numerusform>%n l\xc3\xaaers geskrap</numerusform>',
        b'<numerusform>%n l\xc3\xaaers weg</numerusform>')
    assert bytes(store) == expected


def test_a_plural_target_with_more_strings_adds_forms():
    _original, store = _load()
    unit = _unit(store, '%n files deleted')
    unit.target = multistring(['%n lêer weg', '%n lêers weg', '%n lêertjies weg'])
    assert unit.target.strings == ['%n lêer weg', '%n lêers weg', '%n lêertjies weg']
    assert b'<lengthvariant>%n weg</lengthvariant>' in bytes(store)


def test_a_plural_target_with_fewer_strings_drops_forms():
    _original, store = _load()
    unit = _unit(store, '%n files deleted')
    unit.target = multistring(['%n lêer weg'])
    assert unit.target.strings == ['%n lêer weg']
    assert b'<lengthvariant>%n weg</lengthvariant>' in bytes(store)


def test_a_plain_message_is_written_as_before():
    original, store = _load()
    _unit(store, 'Close').target = 'Sluit'
    assert bytes(store) == original.replace(
        b'<translation>Maak toe</translation>', b'<translation>Sluit</translation>')


def test_reapplying_the_patch_keeps_one_layer():
    importlib.reload(ts2_compat)
    _original, store = _load()
    unit = _unit(store, 'Save the current document')
    unit.target = 'Stoor'
    assert unit.target == 'Stoor'
    assert ts2.tsunit._virtaal_original_target.fget.__module__ == 'translate.storage.ts2'
