#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Pins translate-toolkit storage-format behaviour that real Virtaal
bug reports hit in the past - not code Virtaal itself wraps, so
nothing else in this test suite would catch a future toolkit upgrade
regressing any of these. See each test's own comment for which issue
it guards."""

import io

from translate.storage import xliff


def test_xliff_preserves_a_trailing_non_breaking_space():
    # #2088: a trailing U+00A0 in the target used to get silently
    # dropped on save.
    content = b'''<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file source-language="en" target-language="fr" datatype="plaintext" original="test">
<body>
<trans-unit id="1">
<source xml:space="preserve">Hello\xc2\xa0</source>
<target></target>
</trans-unit>
</body>
</file>
</xliff>
'''
    store = xliff.xlifffile(content)
    store.units[0].target = "Bonjour\xa0"

    buf = io.BytesIO()
    store.serialize(buf)
    reparsed = xliff.xlifffile(buf.getvalue())

    assert reparsed.units[0].target == "Bonjour\xa0"
