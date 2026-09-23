#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.search import match
from translate.storage import po

from virtaal.support.match_compat import matcher


def _matched_quality(source, candidate_source):
    """Run a real match through matcher.matches() -> match.unit2dict(),
    same round-trip currentfile.py's TMModel does."""
    store = po.pofile()
    candidate = po.pounit(candidate_source)
    candidate.target = 'target text'
    store.addunit(candidate)

    results = matcher(store, max_candidates=5, min_similarity=50).matches(source)
    assert len(results) == 1
    return match.unit2dict(results[0])['quality']


# https://github.com/translate/virtaal/issues/3706: a non-integer similarity
# score (the overwhelmingly common case) used to come back as a wildly
# out-of-range "quality" - the digits of its fractional part, misread as the
# whole percentage - because it was embedded unrounded in a PO comment and
# recovered from there with a regex that can't tell integer from fractional
# digits.

def test_matches_reports_a_sane_quality_for_a_non_integer_similarity_score():
    quality = _matched_quality(
        'This is a test string that is fairly long for demonstratio',
        'This is a test string that is fairly long for demonstration',
    )

    assert 0 <= int(quality) <= 100


def test_matches_reports_the_exact_quality_for_an_identical_match():
    quality = _matched_quality('hello world', 'hello world')

    assert quality == '100'


class _FakeComparer:
    """Returns a fixed score per candidate source, regardless of query."""

    def __init__(self, scores):
        self.scores = scores

    def similarity(self, a, b, stoppercentage=40):
        return self.scores[b]


def test_matches_orders_by_the_true_score_even_when_rounded_scores_tie():
    store = po.pofile()
    for source in ('source_aaa', 'source_bbb'):
        candidate = po.pounit(source)
        candidate.target = 'target'
        store.addunit(candidate)

    # Both round to 86%, but source_bbb's true score is higher and should
    # sort first.
    comparer = _FakeComparer({'source_aaa': 85.6, 'source_bbb': 85.9})
    results = matcher(store, max_candidates=5, min_similarity=50, comparer=comparer).matches('abcdefghij')

    assert [unit.source for unit in results] == ['source_bbb', 'source_aaa']
