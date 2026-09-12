#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regenerates devsupport/testfiles/whitespace.{po,xlf,tmx} from the one
case list below - run this after editing CASES, don't hand-edit the
generated files (exotic Unicode space characters are error-prone to
retype correctly by hand across three formats).

Most cases wrap their probe text in guillemets («»), so a mid-string
space shows as a visible gap next to the delimiter even though the
space character itself may be invisible or unusually narrow/wide. The
leading/trailing cases only get a guillemet on the far end - the
whitespace under test must be the string's actual first/last
character (what Virtaal's own leading/trailing-space handling actually
anchors on), not sit behind a visible delimiter.

Targets are deliberately left untranslated - Alt+Down ("copy source to
target") is the intended way to populate them while testing, so the
exact codepoint reaches the target without anyone having to retype an
invisible or exotic Unicode character by hand.
"""

import io

from translate.storage import pypo, tmx, xliff

# Every non-ASCII/invisible character below is spelled as an explicit
# \uXXXX escape, never embedded raw - an embedded NBSP/ZWSP/etc. looks
# identical to its ASCII lookalike (or to nothing at all) in a plain
# text view, making this list unreadable and unsafe to hand-edit.
CASES = [
    ("leading-space", "U+0020 SPACE, leading", " Leading\u00bb"),
    ("trailing-space", "U+0020 SPACE, trailing", "\u00abTrailing "),
    ("double-space", "two U+0020 SPACE in a row, mid-sentence", "\u00abDouble  space\u00bb"),
    ("nbsp-leading", "U+00A0 NO-BREAK SPACE, leading", "\u00a0NBSP leading\u00bb"),
    ("nbsp-trailing", "U+00A0 NO-BREAK SPACE, trailing", "\u00abNBSP trailing\u00a0"),
    ("nbsp-inline", "U+00A0 NO-BREAK SPACE, mid-string (the classic number+unit case)", "\u00ab10\u00a0km\u00bb"),
    ("en-space", "U+2002 EN SPACE", "\u00abEn\u2002space\u00bb"),
    ("em-space", "U+2003 EM SPACE", "\u00abEm\u2003space\u00bb"),
    ("thin-space", "U+2009 THIN SPACE", "\u00abThin\u2009space\u00bb"),
    ("hair-space", "U+200A HAIR SPACE", "\u00abHair\u200aspace\u00bb"),
    ("narrow-nbsp", "U+202F NARROW NO-BREAK SPACE", "\u00abNarrow\u202fNBSP\u00bb"),
    ("figure-space", "U+2007 FIGURE SPACE", "\u00abFigure\u2007space\u00bb"),
    ("punctuation-space", "U+2008 PUNCTUATION SPACE", "\u00abPunctuation\u2008space\u00bb"),
    ("ideographic-space", "U+3000 IDEOGRAPHIC SPACE", "\u00abIdeographic\u3000space\u00bb"),
    ("mathematical-space", "U+205F MEDIUM MATHEMATICAL SPACE", "\u00abMath\u205fspace\u00bb"),
    ("ogham-space-mark", "U+1680 OGHAM SPACE MARK (has a visible glyph in some fonts, unlike the others here)", "\u00abOgham\u1680mark\u00bb"),
    ("zwsp-inline", "U+200B ZERO WIDTH SPACE, mid-word - invisible by design. "
                     "Can't be verified by eye; check with a hex dump/codepoint "
                     "inspector after saving, not by looking at it.", "\u00abZero\u200bwidth\u00bb"),
    ("tab-leading", "U+0009 TAB, leading (bonus - not one of the originally requested cases, but a common real one)", "\tTab leading\u00bb"),
    ("tab-trailing", "U+0009 TAB, trailing (bonus, ditto)", "\u00abTab trailing\t"),
]


def build_po():
    store = pypo.pofile()
    for slug, description, text in CASES:
        unit = store.addsourceunit(text)
        unit.addlocation(slug)
        unit.addnote(description, origin="developer")
    return store


def build_xliff():
    store = xliff.xlifffile()
    for slug, description, text in CASES:
        unit = store.addsourceunit(text)
        unit.addlocation(slug)
        unit.addnote(description, origin="developer")
    return store


def build_tmx():
    store = tmx.tmxfile()
    store.settargetlanguage("en")
    for slug, description, text in CASES:
        # tmx units are always translation pairs (no separate
        # untranslated state) - target mirrors source, since a TM
        # source viewed in Virtaal is read-only anyway (there's no
        # Alt+Down workflow to exercise here as there is for PO/XLIFF).
        store.addsourceunit(text)
        store.units[-1].target = text
        store.units[-1].addnote(f"{slug}: {description}", origin="developer")
    return store


def main():
    for filename, builder in [
        ("whitespace.po", build_po),
        ("whitespace.xlf", build_xliff),
        ("whitespace.tmx", build_tmx),
    ]:
        store = builder()
        buf = io.BytesIO()
        store.serialize(buf)
        with open(filename, "wb") as f:
            f.write(buf.getvalue())
        print(f"Wrote {filename} ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
