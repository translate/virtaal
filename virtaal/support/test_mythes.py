#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.mythes import lookup, parse_thesaurus

# Actual copy (a contiguous chunk, trimmed) of
# pl_PL/th_pl_PL_v2.dat (blob 4bdabb62ec114085e9c01bf8298049959397050e) -
# real diacritics, and a real case of a word ("a") with more than one
# distinct meaning.
SAMPLE_DAT = (
    'UTF-8\n'
    'a|3\n'
    '-|A\n'
    '-|gisis|la|heses\n'
    '-|i|(książkowo) natomiast|oraz|(książkowo) tudzież|(książkowo) zaś\n'
    'abaja|1\n'
    '-|abaja|sukmana|płaszcz|okrycie|burka\n'
    'abakus|2\n'
    '-|(rzadziej) abak\n'
    '-|liczydło|maszyna licząca|arytmometr\n'
).encode()


def test_parse_thesaurus_reads_every_word():
    thesaurus = parse_thesaurus(SAMPLE_DAT)
    assert set(thesaurus) == {'a', 'abaja', 'abakus'}


def test_parse_thesaurus_keeps_every_meaning_for_one_word():
    thesaurus = parse_thesaurus(SAMPLE_DAT)
    assert thesaurus['a'] == [
        ('-', ['A']),
        ('-', ['gisis', 'la', 'heses']),
        ('-', ['i', '(książkowo) natomiast', 'oraz', '(książkowo) tudzież', '(książkowo) zaś']),
    ]


def test_parse_thesaurus_handles_a_single_meaning_word():
    thesaurus = parse_thesaurus(SAMPLE_DAT)
    assert thesaurus['abakus'] == [
        ('-', ['(rzadziej) abak']),
        ('-', ['liczydło', 'maszyna licząca', 'arytmometr']),
    ]


def test_lookup_matches_exact_case_first():
    thesaurus = {'ABC': [('-', ['abecadło'])], 'abc': [('-', ['something else'])]}
    assert lookup(thesaurus, 'ABC') == [('-', ['abecadło'])]


def test_lookup_falls_back_to_lower_case():
    thesaurus = {'abaja': [('-', ['sukmana'])]}
    assert lookup(thesaurus, 'Abaja') == [('-', ['sukmana'])]


def test_lookup_returns_none_for_an_unknown_word():
    thesaurus = parse_thesaurus(SAMPLE_DAT)
    assert lookup(thesaurus, 'nonexistentword') is None
