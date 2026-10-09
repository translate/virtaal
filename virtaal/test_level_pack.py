#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import shutil
import zipfile

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "po", "level-pack.py")

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: de\\n"\n'
TEMPLATE = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "_File"\nmsgstr ""\n\nmsgid "_Redo"\nmsgstr ""\n\n'
            'msgid "Settings"\nmsgstr ""\n\nmsgid "usage: "\nmsgstr ""\n')

pytestmark = pytest.mark.skipif(not shutil.which("msgmerge"), reason="needs gettext's tools")


@pytest.fixture
def packs(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("level_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("TEMPLATE", "PRIORITIES", "LINGUAS"):
        monkeypatch.setattr(module, name, tmp_path / getattr(module, name).name)
    monkeypatch.setattr(module, "PO_DIR", tmp_path)
    (tmp_path / "virtaal.pot").write_text(TEMPLATE, encoding="utf-8")
    (tmp_path / "virtaal.priorities.yaml").write_text(
        "domains:\n  virtaal:\n    '1': [_File]\n    1~: [_Redo]\n    '2': [Settings]\n    '3': ['usage: ']\n",
        encoding="utf-8")
    # _Redo is newer than this catalog; Undo is obsolete.
    (tmp_path / "de.po").write_text(
        HEADER + '\nmsgid "_File"\nmsgstr "_Datei"\n\nmsgid "Settings"\nmsgstr ""\n\n'
        '#~ msgid "Undo"\n#~ msgstr "Rückgängig"\n', encoding="utf-8")
    return module


def test_a_pack_holds_each_level_and_the_priority_file(packs, tmp_path):
    archive = packs.pack("de", tmp_path / "out")

    with zipfile.ZipFile(archive) as zf:
        assert sorted(zf.namelist()) == ["de-level1.po", "de-level2.po", "virtaal.priorities.yaml"]
        level1 = zf.read("de-level1.po").decode("utf-8")
        level2 = zf.read("de-level2.po").decode("utf-8")
    assert 'msgid "_Redo"' in level1 and 'msgid "Settings"' not in level1
    assert 'msgid "Settings"' in level2 and 'msgid "usage: "' not in level2
    assert 'msgstr "_Datei"' in level1
    assert "#~" not in level1
    assert '"X-Priority-File: virtaal.priorities.yaml\\n"' in level1


def _returned(tmp_path, entries):
    path = tmp_path / "returned.po"
    path.write_text(HEADER + '"X-Priority-File: virtaal.priorities.yaml\\n"\n' + entries, encoding="utf-8")
    return path


def test_merge_changes_only_what_the_pack_translates(packs, tmp_path):
    returned = _returned(tmp_path, '\nmsgid "_File"\nmsgstr "_Ablage"\n\nmsgid "_Redo"\nmsgstr "_Wiederholen"\n\n'
                                   'msgid "Settings"\nmsgstr ""\n')

    packs.merge("de", returned)

    text = (tmp_path / "de.po").read_text(encoding="utf-8")
    assert 'msgstr "_Ablage"' in text
    assert 'msgid "_Redo"\nmsgstr "_Wiederholen"' in text
    assert 'msgid "Settings"\nmsgstr ""' in text
    assert "X-Priority-File" not in text
    assert '#~ msgid "Undo"' in text


def test_merge_leaves_a_translation_alone_for_a_fuzzy_one(packs, tmp_path):
    returned = _returned(tmp_path, '\n#, fuzzy\nmsgid "_File"\nmsgstr "_Vielleicht"\n')

    packs.merge("de", returned)

    assert 'msgstr "_Datei"' in (tmp_path / "de.po").read_text(encoding="utf-8")


def test_merge_brings_back_an_obsolete_message_instead_of_doubling_it(packs, tmp_path):
    returned = _returned(tmp_path, '\nmsgid "Undo"\nmsgstr "Zurück"\n')

    packs.merge("de", returned)

    text = (tmp_path / "de.po").read_text(encoding="utf-8")
    assert 'msgid "Undo"\nmsgstr "Zurück"' in text
    assert "#~" not in text


def test_merge_refuses_a_broken_file(packs, tmp_path):
    # msgfmt -c: a msgid and its msgstr must both end in a newline, or neither.
    returned = _returned(tmp_path, '\nmsgid "_File\\n"\nmsgstr "_Datei"\n')
    before = (tmp_path / "de.po").read_text(encoding="utf-8")

    with pytest.raises(SystemExit):
        packs.merge("de", returned)

    assert (tmp_path / "de.po").read_text(encoding="utf-8") == before


LITE_TEMPLATE = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
                 'msgid "Home"\nmsgstr ""\n\nmsgctxt "keyboard label"\nmsgid "Shift"\nmsgstr ""\n\n'
                 'msgid "Bookmarks"\nmsgstr ""\n')


@pytest.fixture
def lite(packs, tmp_path):
    (tmp_path / "lite" / "gtk30").mkdir(parents=True)
    (tmp_path / "lite" / "gtk30" / "gtk30.pot").write_text(LITE_TEMPLATE, encoding="utf-8")
    (tmp_path / "lite" / "iso639-3").mkdir()
    (tmp_path / "virtaal.priorities.yaml").write_text(
        "domains:\n  virtaal:\n    '1': [_File]\n"
        "  gtk30:\n    '1': [Home]\n    1~: [\"keyboard label\\x04Shift\"]\n    '2': [Bookmarks]\n"
        "  iso639-3:\n    '1': [English]\n", encoding="utf-8")
    (tmp_path / "zu.po").write_text(HEADER.replace("de", "zu"), encoding="utf-8")
    packs.LITE_DIR = tmp_path / "lite"
    return packs


def test_a_pack_adds_only_the_library_gaps_at_each_level(lite, tmp_path):
    gaps = {"gtk30": {"Home", "keyboard label\x04Shift", "Bookmarks"}, "iso639-3": {"English"}}

    archive = lite.pack("zu", tmp_path / "out", gaps)

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        gtk = zf.read("gtk30-zu-level1.po").decode("utf-8")
        level2 = zf.read("gtk30-zu-level2.po").decode("utf-8")
        language_names = zf.read("iso639-3-zu-level1.po").decode("utf-8")
    assert {"gtk30-zu-level1.po", "gtk30-zu-level2.po", "iso639-3-zu-level1.po"} <= names
    assert 'msgid "Home"' in gtk and 'msgid "Shift"' in gtk and 'msgid "Bookmarks"' not in gtk
    assert 'msgid "Bookmarks"' in level2
    assert 'msgid "English"\nmsgstr ""' in language_names


def test_a_returned_library_pack_goes_into_its_lite_catalog(lite, tmp_path):
    returned = tmp_path / "gtk30-zu-level1.po"
    returned.write_text(HEADER.replace("de", "zu") + '\nmsgctxt "keyboard label"\nmsgid "Shift"\nmsgstr "Shifu"\n',
                        encoding="utf-8")

    lite.merge("zu", returned)

    catalog = (tmp_path / "lite" / "gtk30" / "zu.po").read_text(encoding="utf-8")
    assert 'msgid "Shift"\nmsgstr "Shifu"' in catalog
    assert 'msgid "Home"' in catalog
    assert 'msgstr "_Datei"' in (tmp_path / "de.po").read_text(encoding="utf-8")


def test_a_returned_language_family_pack_starts_its_lite_catalog(lite, tmp_path):
    returned = tmp_path / "iso639-5-zu-level2.po"
    returned.write_text(HEADER.replace("de", "zu") + '\nmsgid "Songhai languages"\nmsgstr "isiSonghai"\n',
                        encoding="utf-8")

    lite.merge("zu", returned)

    catalog = (tmp_path / "lite" / "iso639-5" / "zu.po").read_text(encoding="utf-8")
    assert 'msgid "Songhai languages"\nmsgstr "isiSonghai"' in catalog
    assert "Songhai" not in (tmp_path / "zu.po").read_text(encoding="utf-8")
