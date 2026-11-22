#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Patches for translate.storage.qm.

translate.storage.qm.qmunit never overrides hasplural() - it's a
static method on the base class that always returns False, unlike
every other plural-capable format (pypo, ts2, cpo, ...). Virtaal's own
plural display/editing (unitview.py) is entirely gated on
unit.hasplural() being correct - without this patch a .qm file's
plural translations are silently limited to one form everywhere,
including an IndexError editing the second+ form. Patched here rather
than upstream for now - a correct fix needs a real translate-toolkit
PR, parked alongside the related NumerusRules gap
(translate/virtaal#1501).

qmfile.parse() decodes every source as ISO-8859-1, but Qt 5 and 6
lrelease write sources as UTF-8 (translate/virtaal#4938)."""

import functools

from translate.misc.multistring import multistring
from translate.storage import qm


def _qm_hasplural(self):
    # Every qm target is wrapped in a multistring, even a singular one
    # ("Open" -> multistring(["Maak oop"])) - only >1 actual string
    # means this unit is really plural. An untranslated plural unit
    # (empty target) still can't be detected this way - there's no
    # NumerusRules data to fall back on (see the module docstring).
    return isinstance(self.target, multistring) and len(self.target.strings) > 1


qm.qmunit.hasplural = _qm_hasplural


_qm_parse = getattr(qm.qmfile.parse, '__wrapped__', qm.qmfile.parse)


def _sources_as_utf8(sources):
    # ISO-8859-1 maps every byte to one character, so encoding it back
    # gives the bytes in the file. Only when every source is valid UTF-8
    # is the file a UTF-8 one; otherwise it's an old Latin-1 file, left
    # as parsed.
    try:
        return [s.encode('iso-8859-1').decode('utf-8') for s in sources]
    except UnicodeError:
        return None


@functools.wraps(_qm_parse)
def _qm_parse_utf8_sources(self, input):
    _qm_parse(self, input)
    sources = _sources_as_utf8([unit.source for unit in self.units])
    if sources is not None:
        for unit, source in zip(self.units, sources):
            unit.source = source


qm.qmfile.parse = _qm_parse_utf8_sources
