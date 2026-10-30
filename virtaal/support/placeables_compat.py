#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""translate-toolkit's EmailPlaceable regex starts with
[A-Za-z0-9]+[-a-zA-Z0-9._%]*, two overlapping repeats that backtrack
cubically over a long run with no "@" after it: a 4096-letter word took
20 s to parse (#4335). [A-Za-z0-9][-a-zA-Z0-9._%]* matches exactly the
same text without the overlap. Upstream bug; drop this once
translate-toolkit fixes it."""

import re

from translate.storage.placeables import general

_SLOW = '[A-Za-z0-9]+[-a-zA-Z0-9._%]*'

if _SLOW in general.EmailPlaceable.regex.pattern:
    general.EmailPlaceable.regex = re.compile(
        general.EmailPlaceable.regex.pattern.replace(_SLOW, '[A-Za-z0-9][-a-zA-Z0-9._%]*'),
        general.EmailPlaceable.regex.flags)
