#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gettext
import importlib.util
import os

import pytest


@pytest.fixture(scope="module")
def generator():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "devsupport", "pseudo-translation", "generate_pseudo_translation.py")
    spec = importlib.util.spec_from_file_location("generate_pseudo_translation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalog(tmp_path, generator, messages, lang="xx", domain="gtk30"):
    mo_dir = tmp_path / lang / "LC_MESSAGES"
    mo_dir.mkdir(parents=True, exist_ok=True)
    generator.write_mo(str(mo_dir / (domain + ".mo")), messages)
    return str(mo_dir / (domain + ".mo"))


def test_tag_messages_tags_every_plural_form_and_keeps_the_context(generator):
    messages = generator.tag_messages(["Stock label\x04_Open", "%u byte\0%u bytes"], "gtk:")

    assert messages == {
        "Stock label\x04_Open": "gtk:_Open",
        "%u byte\0%u bytes": "gtk:%u byte\0gtk:%u bytes",
    }


def test_tag_messages_marks_what_the_lite_template_lacks(generator):
    messages = generator.tag_messages(["Stock label\x04_Open", "_Help", "%u byte\0%u bytes"], "gtk:",
                                      {"Stock label\x04_Open", "%u byte"})

    assert messages == {
        "Stock label\x04_Open": "gtk:_Open",
        "_Help": "gtk!:_Help",
        "%u byte\0%u bytes": "gtk:%u byte\0gtk:%u bytes",
    }


def test_lite_template_keys_match_mo_originals(generator):
    keys = generator.lite_template_keys("glib20")

    assert "format-size\x04%u %s" in keys
    assert "byte" in keys
    assert generator.lite_template_keys("iso639-3") is None


def test_library_locale_dir_is_none_for_a_namespace_this_platform_lacks(generator, monkeypatch):
    import gi

    def unavailable(namespace, version):
        raise ValueError("Namespace %s not available" % namespace)

    monkeypatch.setattr(gi, "require_version", unavailable)

    assert generator.library_locale_dir("GtkosxApplication") is None


def test_tag_messages_leaves_gtks_text_direction_untranslated(generator):
    # GTK reads this message's translation as the UI's text direction.
    assert generator.tag_messages(["default:LTR"], "gtk:") == {}


def test_write_mo_round_trips_through_gettext(tmp_path, generator):
    _catalog(tmp_path, generator, generator.tag_messages(
        ["_Open", "Stock label\x04_Cancel", "%u byte\0%u bytes"], "gtk:"))

    t = gettext.translation("gtk30", str(tmp_path), languages=["xx"])

    assert t.gettext("_Open") == "gtk:_Open"
    assert t.pgettext("Stock label", "_Cancel") == "gtk:_Cancel"
    assert t.ngettext("%u byte", "%u bytes", 1) == "gtk:%u byte"
    assert t.ngettext("%u byte", "%u bytes", 3) == "gtk:%u bytes"


def test_read_mo_originals_skips_the_header(tmp_path, generator):
    path = _catalog(tmp_path, generator, {"Ignore All": "x", "%u byte\0%u bytes": "y\0z"})

    assert sorted(generator.read_mo_originals(path)) == ["%u byte\0%u bytes", "Ignore All"]


def test_fullest_catalog_picks_the_most_messages_and_skips_pseudo_locales(tmp_path, generator):
    _catalog(tmp_path, generator, {"a": "a"}, lang="af")
    fullest = _catalog(tmp_path, generator, {"a": "a", "b": "b"}, lang="de")
    _catalog(tmp_path, generator, {"a": "a", "b": "b", "c": "c"}, lang="pseudo-source")

    assert generator.fullest_catalog([None, str(tmp_path / "missing"), str(tmp_path)], "gtk30") == fullest


def test_fullest_catalog_is_none_without_a_catalog(tmp_path, generator):
    assert generator.fullest_catalog([str(tmp_path)], "gtk30") is None


def test_library_catalogs_are_found_in_ubuntus_language_packs(tmp_path, generator, monkeypatch):
    share = tmp_path / "share"
    (share / "locale").mkdir(parents=True)
    _catalog(share / "locale-langpack", generator, {"_Open": "_Öffnen"}, lang="de")
    monkeypatch.setattr(generator, "library_locale_dir", lambda namespace: str(share / "locale"))
    mo_dir = tmp_path / "pseudo-source"
    mo_dir.mkdir()

    generator._generate_library_mos(str(mo_dir), None)

    assert generator.read_mo_originals(str(mo_dir / "gtk30.mo")) == ["_Open"]
