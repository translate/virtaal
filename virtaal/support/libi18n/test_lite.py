#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gettext

from virtaal.support.libi18n import lite

UPSTREAM_HEADER = "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=(n != 1);\n"
LITE_PO = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "_Open"
msgstr "Lite open"

msgid "_Save"
msgstr "Lite save"

msgctxt "Stock label"
msgid "_Quit"
msgstr "Lite quit"

msgid "%u byte"
msgid_plural "%u bytes"
msgstr[0] "%u greep"
msgstr[1] "%u grepe"

msgid "Untranslated"
msgstr ""
'''


def _write(tmp_path, upstream=None):
    po = tmp_path / "lite.po"
    po.write_text(LITE_PO, encoding="utf-8")
    upstream_mo = None
    if upstream is not None:
        upstream_mo = str(tmp_path / "upstream.mo")
        lite.write_mo(upstream_mo, dict(upstream, **{"": UPSTREAM_HEADER}))
    out_dir = tmp_path / "out"
    lite.merge(upstream_mo, str(po), str(out_dir / "xx" / "LC_MESSAGES" / "gtk30.mo"))
    return gettext.translation("gtk30", str(out_dir), languages=["xx"])


def test_merge_keeps_upstreams_translation_and_fills_the_rest_from_lite(tmp_path):
    t = _write(tmp_path, upstream={"_Open": "Upstream open", "Only upstream": "Upstream only"})

    assert t.gettext("_Open") == "Upstream open"
    assert t.gettext("Only upstream") == "Upstream only"
    assert t.gettext("_Save") == "Lite save"
    assert t.pgettext("Stock label", "_Quit") == "Lite quit"
    assert t.ngettext("%u byte", "%u bytes", 2) == "%u grepe"


def test_merge_without_an_upstream_catalog_is_the_lite_catalog(tmp_path):
    t = _write(tmp_path, upstream=None)

    assert t.gettext("_Open") == "Lite open"
    assert t.gettext("Untranslated") == "Untranslated"


def test_merge_ignores_an_upstream_message_without_a_translation(tmp_path):
    t = _write(tmp_path, upstream={"_Save": ""})

    assert t.gettext("_Save") == "Lite save"


def test_read_mo_round_trips_contexts_and_plurals(tmp_path):
    path = str(tmp_path / "x.mo")
    messages = {"": UPSTREAM_HEADER, "Stock label\x04_Quit": "Q", "%u byte\0%u bytes": "a\0b"}
    lite.write_mo(path, messages)

    assert lite.read_mo(path) == messages


def test_mismatched_catalogs_flags_another_copy_at_our_destination():
    mo_files = [("/repo/mo/zu/gtk30.mo", "share/locale/zu/LC_MESSAGES")]
    ours = ("share/locale/zu/LC_MESSAGES/gtk30.mo", "/repo/mo/zu/gtk30.mo", "DATA")
    gtks = ("share/locale/zu/LC_MESSAGES/gtk30.mo", "/opt/gtk/share/locale/zu/LC_MESSAGES/gtk30.mo", "DATA")
    other = ("share/locale/de/LC_MESSAGES/gtk30.mo", "/opt/gtk/share/locale/de/LC_MESSAGES/gtk30.mo", "DATA")

    assert lite.mismatched_catalogs([ours, other], mo_files) == []
    assert lite.mismatched_catalogs([gtks, other], mo_files) == [
        ("share/locale/zu/LC_MESSAGES/gtk30.mo", gtks[1], "/repo/mo/zu/gtk30.mo")]


def test_library_locale_dir_is_none_for_a_missing_library():
    assert lite.library_locale_dir("NoSuchNamespace") is None
