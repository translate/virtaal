#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""translate-toolkit's FluentFile.parse() passes a UTF-8 byte order mark
on to the Fluent parser, which expects an entry at offset 0, so a .ftl
file saved with one (Windows editors often add it) can't be opened
(#4413). Upstream bug; drop this once translate-toolkit strips it."""

from codecs import BOM_UTF8

try:
    from translate.storage import fluent
except ImportError:  # fluent.syntax missing: only .ftl files fail, not start-up
    fluent = None


def _patch(file_class):
    parse = file_class.parse

    def compat_parse(self, fluentsrc):
        if isinstance(fluentsrc, bytes) and fluentsrc.startswith(BOM_UTF8):
            fluentsrc = fluentsrc[len(BOM_UTF8):]
        parse(self, fluentsrc)

    file_class.parse = compat_parse


if fluent is not None:
    _patch(fluent.FluentFile)
