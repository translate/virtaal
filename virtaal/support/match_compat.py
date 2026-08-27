# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Compatibility shim around translate-toolkit's search.match.matcher.

matcher.matches() keeps its running top-N candidates in a fixed-size
min-heap of (similarity, candidate) tuples, via heapq.heapreplace().
When two candidates tie on similarity, heapq's own sift-up/sift-down
rebalancing falls through to comparing the *second* tuple element (the
candidate, a TranslationUnit) to break the tie - and TranslationUnit
defines no ordering:

    TypeError: '<' not supported between instances of 'TranslationUnit'
    and 'TranslationUnit'

The "Current File" TM plugin (virtaal/plugins/tm/models/currentfile.py,
the only caller of the plain matcher class in this codebase -
terminologymatcher, the other subclass, overrides matches() with its
own non-heap implementation and isn't affected) crashes with exactly
this traceback querying a file with two equal-similarity candidate
units. Reproducible any time two or more candidates tie on similarity,
not an edge case - short/simple source strings make ties routine.

It's an upstream bug, not anything Virtaal's own TM matching does
wrong, but Virtaal can't wait for a translate-toolkit release to fix
its own in-app TM lookup - this subclass adds a tiebreaker to the heap
tuples locally instead, same shape of fix as pogrep_compat.py's.

Remove this shim (and go back to importing matcher directly in
virtaal/plugins/tm/models/currentfile.py) once the installed
translate-toolkit no longer needs it.
"""

import heapq
from itertools import count
from operator import itemgetter

from translate.search.match import matcher as _UpstreamMatcher
from translate.search.match import sourcelen


class matcher(_UpstreamMatcher):
    """matcher with the heapq tie-breaking crash fixed."""

    def matches(self, text):
        # Identical to upstream's matches() except the heap tuples carry
        # an extra, always-comparable tiebreaker (a monotonic counter)
        # between the similarity score and the candidate itself, so
        # heapq never needs to compare two TranslationUnits directly -
        # see module docstring above for why that matters.
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
        bestcandidates.sort(key=itemgetter(0), reverse=True)
        return self.buildunits(bestcandidates)
