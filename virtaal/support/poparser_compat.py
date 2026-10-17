#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""translate-toolkit 3.19.0+ restarts a PO parse in the header's charset
but leaves PoParseState._current_encoding at UTF-8, so a PO file in
ISO-8859-1, KOI8-R, ... with any non-ASCII text fails with
UnicodeDecodeError (#4390). Upstream bug; drop this once
translate-toolkit fixes PoParseState.set_encoding()."""

from translate.storage import poparser


def _patch(state_class):
    set_encoding = state_class.set_encoding

    def compat_set_encoding(self, encoding):
        # read_line() decodes with _current_encoding.
        self._current_encoding = encoding
        set_encoding(self, encoding)

    state_class.set_encoding = compat_set_encoding


# translate-toolkit 3.18.1 and earlier (3.17.5 is the Python 3.10 pin)
# read these files correctly and have no PoParseState._current_encoding.
_state_class = getattr(poparser, "PoParseState", None)
if _state_class is not None and "_current_encoding" in _state_class.__init__.__code__.co_names:
    _patch(_state_class)
