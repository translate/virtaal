#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Compatibility shim around translate-toolkit's pogrep.GrepFilter.

GrepFilter.getmatches() always ORs re.LOCALE into its flags, even
though it only ever compiles str patterns - Python 3.14+ raises
"ValueError: cannot use LOCALE flag with a str pattern" instead of
silently accepting it, crashing every search/replace. It also wraps
the pattern in a group, which moves a leading inline flag such as
"(?i)" off the start - an error since Python 3.11. Upstream bugs;
drop this shim once translate-toolkit fixes them.

The shim also stops at max_matches instead of raising ValueError, which
the search never caught (#4395), and runs an expression that can take
exponential time in a child process with a time limit, raising
SearchTimeout if it's stopped (#4692); keep those when the rest goes.
"""

import re

from translate.lang import data
from translate.tools.pogrep import GrepFilter as _UpstreamGrepFilter

from virtaal.support import regexsearch
from virtaal.support.regexsearch import SearchTimeout  # noqa: F401


class _Match:
    def __init__(self, start, end):
        self._start = start
        self._end = end

    def start(self):
        return self._start

    def end(self):
        return self._end


class _FoundSpans:
    """Stands in for the compiled expression in find_matches(), with
        the matches a child process found."""

    def __init__(self, spans):
        self.spans = spans

    def finditer(self, string):
        return [_Match(*span) for span in self.spans.get(string, ())]


class GrepFilter(_UpstreamGrepFilter):
    """GrepFilter with the re.LOCALE and inline-flag errors fixed."""

    def getmatches(self, units):
        if not self.searchstring:
            return [], []

        searchstring = self.searchstring
        # Same flags as upstream, minus re.LOCALE (invalid for str
        # patterns - see module docstring above).
        flags = re.MULTILINE | re.UNICODE

        if self.ignorecase:
            flags |= re.IGNORECASE
        if not self.useregexp:
            searchstring = re.escape(searchstring)
        self.re_search = re.compile(searchstring, flags)
        pattern = self.re_search
        if self.useregexp and regexsearch.is_risky(searchstring, flags):
            strings = {
                data.normalize(string)
                for unit in units
                for _part, unit_strings in self._parts(unit)
                for string in unit_strings
                if string
            }
            strings = sorted(strings)
            spans = regexsearch.find_spans(searchstring, flags, strings)
            pattern = _FoundSpans(dict(zip(strings, spans)))

        # Everything below here is upstream's getmatches(), except that
        # it stops at max_matches instead of raising.
        from translate.tools.pogrep import find_matches

        matches = []
        indexes = []

        for index, unit in enumerate(units):
            old_length = len(matches)

            for part, unit_strings in self._parts(unit):
                matches.extend(find_matches(unit, part, unit_strings, pattern))

            if len(matches) > old_length:
                old_length = len(matches)
                indexes.append(index)

            # Upstream raises ValueError here; stop at the limit instead,
            # keeping the matches found so far (#4395).
            if self.max_matches and len(matches) >= self.max_matches:
                del matches[self.max_matches:]
                break

        return matches, indexes

    def _parts(self, unit):
        """The (part, strings) of unit to search, in upstream's order."""
        if self.search_target:
            yield "target", unit.target.strings if unit.hasplural() else [unit.target]
        if self.search_source:
            yield "source", unit.source.strings if unit.hasplural() else [unit.source]
        if self.search_notes:
            yield "notes", unit.getnotes()
        if self.search_locations:
            yield "locations", unit.getlocations()
