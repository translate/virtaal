#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Compatibility shim around translate-toolkit's search.match.matcher.

Fixes two upstream bugs:

- matcher.matches() keeps its top-N candidates in a min-heap of
  (similarity, candidate) tuples; on a similarity tie, heapq falls back
  to comparing the candidates themselves, and TranslationUnit defines no
  ordering - "TypeError: '<' not supported between instances of
  'TranslationUnit' and 'TranslationUnit'".

- matcher.buildunits() embeds the raw, unrounded similarity float in the
  candidate's PO comment as e.g. "98.30508474576271%". match.unit2dict()
  later recovers the quality from that comment with the regex
  r"([0-9]+)%", which greedily grabs whatever digit run immediately
  precedes the "%" - for a non-integer score that's the tail of the
  fractional part (here "30508474576271"), not the integer percentage.
  Round the score to a whole percent before it reaches buildunits(), so
  the note has no decimal point left to confuse the regex - #3706.

Both are upstream bugs; drop this shim once translate-toolkit fixes them.
"""

import heapq
from itertools import count
from operator import itemgetter

from translate.search.match import matcher as _UpstreamMatcher
from translate.search.match import sourcelen


class matcher(_UpstreamMatcher):
    """matcher with the heapq tie-breaking crash and the quality-note
    rounding bug fixed."""

    def matches(self, text):
        # Identical to upstream, except the heap tuples carry an extra
        # monotonic tiebreaker so heapq never compares candidates directly.
        tiebreaker = count()
        bestcandidates = [(0.0, next(tiebreaker), None)] * self.MAX_CANDIDATES
        min_similarity = self.MIN_SIMILARITY

        startlength = self.getstartlength(min_similarity, text)
        startindex = 0
        endindex = len(self.candidates.units)
        while startindex < endindex:
            mid = (startindex + endindex) // 2
            if sourcelen(self.candidates.units[mid]) < startlength:
                startindex = mid + 1
            else:
                endindex = mid

        stoplength = self.getstoplength(min_similarity, text)
        lowestscore = 0

        for candidate in self.candidates.units[startindex:]:
            cmpstring = candidate.source
            if len(cmpstring) > stoplength:
                break
            similarity = self.comparer.similarity(text, cmpstring, min_similarity)
            if similarity < min_similarity:
                continue
            if similarity > lowestscore:
                heapq.heapreplace(bestcandidates, (similarity, next(tiebreaker), candidate))
                lowestscore = bestcandidates[0][0]
                if lowestscore >= 100:
                    break
                if min_similarity < lowestscore:
                    min_similarity = lowestscore
                    stoplength = self.getstoplength(min_similarity, text)

        # Remove the empty ones, drop the tiebreaker (buildunits() below
        # expects plain (score, candidate) pairs, same as upstream).
        bestcandidates = [(item[0], item[2]) for item in bestcandidates if item[0] != 0]
        # Sort on the exact score, then round only for buildunits() - see
        # the module docstring. Rounding before the sort would let two
        # close scores (e.g. 85.6 and 85.3) tie and lose their real order.
        bestcandidates.sort(key=itemgetter(0), reverse=True)
        bestcandidates = [(round(score), candidate) for score, candidate in bestcandidates]
        return self.buildunits(bestcandidates)
