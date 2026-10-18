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
translate-toolkit fixes PoParseState.set_encoding().

A header charset that isn't ASCII-compatible (UTF-16, UTF-32) can't be
right for a PO file, which is read as ASCII-compatible lines; it is
usually a wrong header on a UTF-8 file. Such a file is read as UTF-8,
and saved as UTF-8 with charset=UTF-8 (#4409). Virtaal's own choice:
keep it when the rest goes."""

import re

from translate.storage import poparser, pypo

_CHARSET_RE = re.compile(rb"charset=([A-Za-z0-9_.:-]+)")


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


def _ascii_compatible(charset):
    try:
        return "a\n".encode(charset) == b"a\n"
    except LookupError:
        return True  # translate-toolkit reports the unknown charset


def _rescue_charset(data):
    """C{data} with a header charset that isn't ASCII-compatible named
        UTF-8 instead, unless the bytes really are UTF-16 or UTF-32."""
    header = data.split(b"\n\n", 1)[0]
    match = _CHARSET_RE.search(header)
    if not match or b"\x00" in header:
        return data
    if _ascii_compatible(match.group(1).decode("ascii")):
        return data
    return data[:match.start(1)] + b"UTF-8" + data[match.end(1):]


_parse = pypo.pofile.parse


def _compat_parse(self, input):
    if hasattr(input, "name"):
        self.filename = input.name
    if not isinstance(input, bytes):
        input = input.read()
    _parse(self, _rescue_charset(input))


pypo.pofile.parse = _compat_parse
