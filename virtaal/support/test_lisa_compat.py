#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import codecs
import io

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


UTF16_TMX = """<?xml version="1.0" encoding="UTF-16"?>
<tmx version="1.4"><header creationtool="x" creationtoolversion="1"
  segtype="sentence" o-tmf="x" adminlang="en-US" srclang="en-US"
  datatype="plaintext"/><body>
<tu><tuv xml:lang="en-US"><seg>Hello</seg></tuv>
<tuv xml:lang="de-DE"><seg>Hallo</seg></tuv></tu>
</body></tmx>"""


def _utf16(text, bom, codec):
    return bom + text.encode(codec)


def test_translate_toolkit_still_writes_a_second_byte_order_mark(monkeypatch):
    # Once this fails translate-toolkit writes one BOM itself, and the
    # serialize() patch can go.
    store = tmx.tmxfile.parsestring(_utf16(UTF16_TMX, codecs.BOM_UTF16_LE, "utf-16-le"))
    monkeypatch.setattr(store, "serialize_hook", lambda text: text.encode(store.encoding))
    out = io.BytesIO()

    lisa_compat._serialize(store, out)

    assert out.getvalue().count("".encode("utf-16")) == 2


@pytest.mark.parametrize(
    ("bom", "codec"),
    [(codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")],
)
def test_a_tmx_declared_as_utf16_saves_with_one_byte_order_mark(bom, codec):
    store = tmx.tmxfile.parsestring(_utf16(UTF16_TMX, bom, codec))
    store.units[0].target = "Grüß Gott"

    saved = bytes(store)

    assert saved.startswith(bom + '<?xml version="1.0" encoding="UTF-16"?>'.encode(codec))
    assert saved[len(bom) :].decode(codec).count("﻿") == 0
    assert tmx.tmxfile.parsestring(saved).units[0].target == "Grüß Gott"


def test_an_xliff_declared_as_utf16_saves_with_one_byte_order_mark():
    text = PI_XLIFF.decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    store = xliff.xlifffile.parsestring(_utf16(text, codecs.BOM_UTF16_LE, "utf-16-le"))
    store.units[0].target = "Goeiedag"

    saved = bytes(store)

    assert saved[2:].decode("utf-16-le").count("﻿") == 0
    assert xliff.xlifffile.parsestring(saved).units[0].target == "Goeiedag"


def test_a_utf16_tmx_without_an_encoding_declaration_stays_utf16():
    # Trados Workbench exports have a BOM and no encoding declaration.
    text = UTF16_TMX.replace(' encoding="UTF-16"', "")
    store = tmx.tmxfile.parsestring(_utf16(text, codecs.BOM_UTF16_LE, "utf-16-le"))
    store.units[0].target = "Grüß Gott"

    saved = bytes(store)

    assert saved.startswith(codecs.BOM_UTF16_LE + b"<\x00?\x00x\x00m\x00l\x00")
    assert 'encoding="utf-16"' in saved[2:].decode("utf-16-le").lower()
    assert tmx.tmxfile.parsestring(saved).units[0].target == "Grüß Gott"


def test_a_utf8_tmx_stays_utf8():
    store = tmx.tmxfile.parsestring(TMX)

    assert bytes(store).startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<tmx')


def test_a_utf16_file_opened_from_disk_stays_utf16(tmp_path):
    path = tmp_path / "workbench.tmx"
    path.write_bytes(
        _utf16(UTF16_TMX.replace(' encoding="UTF-16"', ""), codecs.BOM_UTF16_LE, "utf-16-le")
    )
    store = tmx.tmxfile.parsefile(str(path))
    store.units[0].target = "Servus"

    store.save()

    data = path.read_bytes()
    assert data.startswith(codecs.BOM_UTF16_LE)
    assert tmx.tmxfile.parsestring(data).units[0].target == "Servus"


ASCII_TMX = b"""<?xml version="1.0" encoding="us-ascii"?>
<tmx version="1.4"><header creationtool="x" creationtoolversion="1"
  segtype="sentence" o-tmf="x" adminlang="en-US" srclang="en-US"
  datatype="plaintext"/><body>
<tu><tuv xml:lang="en-US"><seg>R&#233;sum&#233;</seg></tuv>
<tuv xml:lang="fr-FR"><seg>R&#xe9;sum&#xe9;</seg></tuv></tu>
</body></tmx>"""


def test_translate_toolkit_still_fails_on_text_its_encoding_cant_hold():
    # Once this fails translate-toolkit escapes such text itself, and the
    # serialize_hook() patch can go.
    store = tmx.tmxfile.parsestring(ASCII_TMX)

    with pytest.raises(UnicodeEncodeError):
        lisa_compat._serialize_hook(store, store.units[0].source)


def test_text_an_ascii_tmx_cant_hold_is_saved_as_character_references():
    store = tmx.tmxfile.parsestring(ASCII_TMX)
    store.units[0].target = "Crème brûlée"

    saved = bytes(store)

    saved.decode("ascii")
    assert b"Cr&#232;me br&#251;l&#233;e" in saved
    reopened = tmx.tmxfile.parsestring(saved).units[0]
    assert (reopened.source, reopened.target) == ("Résumé", "Crème brûlée")
