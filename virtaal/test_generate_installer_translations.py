#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import sys

import pytest

SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "devsupport", "packaging", "windows", "generate_installer_translations.py",
)


@pytest.fixture
def gen():
    spec = importlib.util.spec_from_file_location("generate_installer_translations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_linguas_code_has_an_installer_decision(gen):
    # Fails when a translation is added to po/LINGUAS - map it to a
    # vendored .isl or list it in NO_INNO_LANGUAGE.
    gen.installer_languages(gen.read_linguas())


def test_mapped_and_unmapped_are_disjoint(gen):
    assert not set(gen.INNO_LANGUAGES) & gen.NO_INNO_LANGUAGE


def test_vendored_files_match_the_mapping(gen):
    vendored = {p.name for p in gen.LANGUAGES_DIR.iterdir()}
    assert vendored == set(gen.INNO_LANGUAGES.values())


def test_every_message_is_in_the_pot(gen):
    # A msgid missing from the POT never gets translated, silently
    # leaving that installer string in English.
    from translate.storage import pypo
    pot = pypo.pofile((gen.REPO_ROOT / "po" / "virtaal.pot").read_bytes())
    msgids = {unit.source for unit in pot.units}
    assert set(gen.MESSAGE_KEY_TO_MSGID.values()) <= msgids


def test_unmapped_code_is_an_error(gen):
    with pytest.raises(ValueError, match="xx"):
        gen.installer_languages(["de", "xx"])


def test_only_linguas_languages_are_offered(gen):
    include = gen.build_include(["de", "zu", "af"])
    languages = include.split("[CustomMessages]")[0]
    assert languages.splitlines() == [
        "[Languages]",
        'Name: "english"; MessagesFile: "compiler:Default.isl"',
        'Name: "afrikaans"; MessagesFile: "languages\\Afrikaans.isl"',
        'Name: "german"; MessagesFile: "languages\\German.isl"',
        "",
    ]


def test_custom_messages_skip_fuzzy_and_untranslated(gen, tmp_path, monkeypatch):
    (tmp_path / "po").mkdir()
    (tmp_path / "po" / "de.po").write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "TBX Glossary"\nmsgstr "TBX-Glossar"\n\n'
        '#, fuzzy\nmsgid "Qt Phrase Book"\nmsgstr "Qt-Phrasenbuch"\n\n'
        'msgid "Qt Message File"\nmsgstr ""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(gen, "REPO_ROOT", tmp_path)
    lines = gen.build_custom_messages(["de"])
    assert "german.TbxFileType=TBX-Glossar" in lines
    assert "TbxFileType=TBX Glossary" in lines
    assert not any(line.startswith(("german.QphFileType", "german.QmFileType")) for line in lines)


def test_main_writes_bom_and_rejects_unmapped(gen, tmp_path, monkeypatch):
    out = tmp_path / "installer-strings.iss"
    monkeypatch.setattr(gen, "read_linguas", lambda: ["de"])
    monkeypatch.setattr(sys, "argv", ["gen", str(out)])
    gen.main()
    assert out.read_bytes().startswith(b"\xef\xbb\xbf[Languages]")

    monkeypatch.setattr(gen, "read_linguas", lambda: ["xx"])
    with pytest.raises(SystemExit) as exc:
        gen.main()
    assert exc.value.code == 1
