#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from lxml import etree
from translate.misc import xml_helpers
from translate.storage import tmx, xliff
from translate.storage.placeables import StringElem

from virtaal.support import lisa_compat

TMX = b"""<?xml version="1.0" encoding="utf-8"?>
<tmx version="1.4"><header creationtool="x" creationtoolversion="1"
  segtype="sentence" o-tmf="x" adminlang="en-US" srclang="en-US"
  datatype="plaintext"/><body>
<tu><tuv xml:lang="en-US"><seg><ph x="1"/>Hello world</seg></tuv>
<tuv xml:lang="de-DE"><seg><ph x="1"/>Hallo Welt</seg></tuv></tu>
</body></tmx>"""


def _tmx_unit():
    return tmx.tmxfile.parsestring(TMX).units[0]


def _reopened(unit):
    return tmx.tmxfile.parsestring(bytes(unit._store)).units[0]


def test_translate_toolkit_still_keeps_the_old_inline_content():
    # Once this fails translate-toolkit replaces the target itself, and
    # lisa_compat can go.
    unit = _tmx_unit()
    settarget = type(unit).settarget
    while hasattr(settarget, "ttk_settarget"):
        settarget = settarget.ttk_settarget

    settarget(unit, "Neu")

    assert unit.target == "NeuHallo Welt"


def test_a_new_tmx_translation_replaces_the_old_one():
    unit = _tmx_unit()

    unit.target = "Neu"

    assert b"<seg>Neu</seg>" in bytes(unit._store)
    assert _reopened(unit).target == "Neu"


def test_typing_at_the_start_does_not_repeat_the_old_text():
    unit = _tmx_unit()

    unit.rich_target = [StringElem("Neu Hallo Welt")]

    assert _reopened(unit).target == "Neu Hallo Welt"


def test_an_unchanged_target_keeps_its_inline_elements():
    unit = _tmx_unit()

    unit.target = "Hallo Welt"

    assert b'<seg><ph x="1"/>Hallo Welt</seg>' in bytes(unit._store)


def test_the_source_is_untouched():
    unit = _tmx_unit()

    unit.target = "Neu"

    assert b'<seg><ph x="1"/>Hello world</seg>' in bytes(unit._store)


def test_a_plain_xliff_target_replaces_its_inline_elements():
    data = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">'
        b'<file original="a" datatype="plaintext" source-language="en" target-language="de">'
        b'<body><trans-unit id="1"><source>Hi</source>'
        b'<target><g id="1">alt</g> Rest</target></trans-unit></body></file></xliff>'
    )
    unit = xliff.xlifffile.parsestring(data).units[0]

    unit.target = "Neu"

    assert unit.target == "Neu"


PI_XLIFF = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="x.txt" source-language="en" target-language="af" datatype="plaintext">
<body><trans-unit id="1"><?my-tool keep?><source>Hello</source><target>Hallo</target>
</trans-unit></body></file></xliff>"""


def test_translate_toolkit_still_fails_to_reindent_a_processing_instruction(monkeypatch):
    # Once this fails translate-toolkit skips processing instructions
    # itself, and the reindent() patch can go.
    store = xliff.xlifffile.parsestring(PI_XLIFF)
    monkeypatch.setattr(xml_helpers, "reindent", lisa_compat.reindent.ttk_reindent)

    with pytest.raises(AttributeError):
        xml_helpers.reindent(store.document.getroot(), **store.XMLindent)


def test_an_xliff_with_a_processing_instruction_in_a_unit_saves():
    store = xliff.xlifffile.parsestring(PI_XLIFF)
    store.units[0].target = "Goeiedag"

    saved = bytes(store)

    reopened = xliff.xlifffile.parsestring(saved)
    assert reopened.units[0].target == "Goeiedag"
    trans_unit = reopened.units[0].xmlelement
    assert trans_unit[0].tag is etree.PI
    assert (trans_unit[0].target, trans_unit[0].text) == ("my-tool", "keep")
