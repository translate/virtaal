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

"""Compatibility shim around translate-toolkit's pogrep.GrepFilter.

translate.tools.pogrep.GrepFilter.getmatches() always ORs re.LOCALE into
its flags, even though it only ever compiles ``str`` patterns (never
``bytes``). Older Pythons silently accepted that combination (re.LOCALE
is meaningless for str patterns - case folding for str is always
Unicode-based), but Python's own re module now rejects it outright:

    ValueError: cannot use LOCALE flag with a str pattern

This turns every search (Ctrl+F), Replace, and quality-check/placeable
navigation that goes through search into a hard crash on Python 3.14+
(confirmed via a real local run with checks.po, and via translate-
toolkit's own pogrep.py:255 traceback). It's an upstream bug, not
anything Virtaal's own search UI does wrong - reported upstream, but
Virtaal can't wait for a translate-toolkit release to fix its own
in-app search, so this subclass drops the bogus flag locally instead.

Remove this shim (and go back to importing GrepFilter directly in
virtaal/modes/searchmode.py) once the installed translate-toolkit no
longer needs it.
"""

import re

from translate.tools.pogrep import GrepFilter as _UpstreamGrepFilter


class GrepFilter(_UpstreamGrepFilter):
    """GrepFilter with the re.LOCALE/str-pattern crash fixed."""

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
        self.re_search = re.compile(f"({searchstring})", flags)

        # Everything below here is unchanged from upstream's
        # getmatches() - only the flags above differ.
        from translate.tools.pogrep import find_matches

        matches = []
        indexes = []

        for index, unit in enumerate(units):
            old_length = len(matches)

            if self.search_target:
                targets = unit.target.strings if unit.hasplural() else [unit.target]
                matches.extend(find_matches(unit, "target", targets, self.re_search))
            if self.search_source:
                sources = unit.source.strings if unit.hasplural() else [unit.source]
                matches.extend(find_matches(unit, "source", sources, self.re_search))
            if self.search_notes:
                matches.extend(
                    find_matches(unit, "notes", unit.getnotes(), self.re_search)
                )

            if self.search_locations:
                matches.extend(
                    find_matches(unit, "locations", unit.getlocations(), self.re_search)
                )

            # A search for a single letter or an all-inclusive regular
            # expression could give enough results to cause performance
            # problems. The answer is probably not very useful at this scale.
            if self.max_matches and len(matches) > self.max_matches:
                raise ValueError("Too many matches found")

            if len(matches) > old_length:
                old_length = len(matches)
                indexes.append(index)

        return matches, indexes
