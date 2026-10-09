#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gettext
import os

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


def test_merge_without_a_lite_catalog_is_the_upstream_catalog(tmp_path):
    upstream_mo = str(tmp_path / "upstream.mo")
    lite.write_mo(upstream_mo, {"": UPSTREAM_HEADER, "_Open": "Upstream open"})
    out_dir = tmp_path / "out"

    lite.merge(upstream_mo, None, str(out_dir / "xx" / "LC_MESSAGES" / "gtk30.mo"))

    assert gettext.translation("gtk30", str(out_dir), languages=["xx"]).gettext("_Open") == "Upstream open"


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


def test_read_linguas_skips_comments_and_blank_lines(tmp_path):
    (tmp_path / "LINGUAS").write_text("# shipped\naf\n\nzu  # Zulu\n", encoding="utf-8")

    assert lite.read_linguas(tmp_path / "LINGUAS") == ["af", "zu"]


def test_bundle_languages_adds_what_gettext_falls_back_to():
    assert lite.bundle_languages(["pt_BR", "sr@latin", "de"]) == ["de", "pt", "pt_BR", "sr", "sr@latin"]


def _dest(lang, domain):
    return os.path.normpath("share/locale/%s/LC_MESSAGES/%s.mo" % (lang, domain))


def test_expected_catalogs_follow_the_hosts_libraries_and_our_lite_catalogs(tmp_path, monkeypatch):
    upstream = tmp_path / "gtk" / "share" / "locale"
    (upstream / "de" / "LC_MESSAGES").mkdir(parents=True)
    (upstream / "de" / "LC_MESSAGES" / "gtk30.mo").write_bytes(b"")
    monkeypatch.setattr(lite, "library_locale_dir", lambda ns: str(upstream) if ns == "Gtk" else None)
    mo_files = [("/repo/mo/zu/gtk30.mo", os.path.join("share", "locale", "zu", "LC_MESSAGES"))]

    expected = lite.expected_catalogs(["de", "ff", "zu"], mo_files)

    assert expected == {_dest("de", "virtaal"), _dest("ff", "virtaal"), _dest("zu", "virtaal"),
                        _dest("de", "gtk30"), _dest("zu", "gtk30")}


def test_missing_catalogs_lists_expected_destinations_not_bundled():
    datas = [(_dest("de", "virtaal"), "/repo/mo/de/virtaal.mo", "DATA"),
             (_dest("de", "gtk30"), "/opt/gtk/de/gtk30.mo", "DATA")]
    expected = {_dest("de", "virtaal"), _dest("de", "gtk30"), _dest("zu", "virtaal"), _dest("de", "glib20")}

    assert lite.missing_catalogs(datas, expected) == sorted([_dest("de", "glib20"), _dest("zu", "virtaal")])


def test_is_unused_catalog_drops_unread_library_and_pycountry_domains():
    def pycountry(lang, domain):
        return os.path.normpath("pycountry/locales/%s/LC_MESSAGES/%s.mo" % (lang, domain))

    unused = [_dest("de", "atk10"), _dest("de", "gdk-pixbuf"), _dest("zu", "gtkspell3"),
              pycountry("de", "iso3166-2"), pycountry("de", "iso4217"), pycountry("de", "iso15924")]
    used = [_dest("de", "gtk30"), _dest("de", "glib20"), _dest("de", "virtaal"),
            pycountry("hi", "iso639-3"), pycountry("hi", "iso3166-1"),
            os.path.normpath("pycountry/databases/iso4217.json")]

    assert [d for d in unused + used if lite.is_unused_catalog(d)] == unused


def test_library_locale_dir_is_none_for_a_missing_library():
    assert lite.library_locale_dir("NoSuchNamespace") is None
