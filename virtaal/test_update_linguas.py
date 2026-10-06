#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import shutil

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "po", "update-linguas.py")

pytestmark = pytest.mark.skipif(not shutil.which("msgmerge"), reason="needs gettext's msgmerge")

TEMPLATE = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "One"\nmsgstr ""\n\nmsgid "Two"\nmsgstr ""\n\n'
            'msgid "Three"\nmsgstr ""\n\nmsgid "Four"\nmsgstr ""\n')


def _po(**targets):
    """A catalog translating the template's msgids given as keyword
        arguments; a value of None marks one fuzzy."""
    text = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
    for msgid, target in targets.items():
        fuzzy = "#, fuzzy\n" if target is None else ""
        text += '\n%smsgid "%s"\nmsgstr "%s"\n' % (fuzzy, msgid, target or "x")
    return text


@pytest.fixture
def linguas(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("update_linguas", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "PO_DIR", tmp_path)
    monkeypatch.setattr(module, "LINGUAS", tmp_path / "LINGUAS")
    monkeypatch.setattr(module, "TEMPLATE", tmp_path / "virtaal.pot")
    monkeypatch.setattr(module, "EXCLUDED", {"ach": "reasons"})
    (tmp_path / "virtaal.pot").write_text(TEMPLATE, encoding="utf-8")
    (tmp_path / "de.po").write_text(_po(One="Eins", Two="Zwei"), encoding="utf-8")
    (tmp_path / "vi.po").write_text(_po(One="Một", Two=None), encoding="utf-8")
    (tmp_path / "ach.po").write_text(_po(One="a", Two="b", Three="c", Four="d"), encoding="utf-8")
    (tmp_path / "en_ZA.po").write_text(_po(), encoding="utf-8")
    return module


def test_coverage_counts_translated_messages_not_fuzzy_ones(linguas, tmp_path):
    percents, _ = linguas.expected([])

    assert percents == {"ach": 100, "de": 50, "en_ZA": 0, "vi": 25}


def test_ships_above_threshold_english_variants_and_not_excluded(linguas):
    _, ships = linguas.expected([])

    assert ships == ["de", "en_ZA"]


def test_keeps_a_shipped_language_below_threshold_until_removals_are_enforced(linguas, monkeypatch):
    assert linguas.expected(["vi", "ach"])[1] == ["de", "en_ZA", "vi"]

    monkeypatch.setattr(linguas, "ENFORCE_REMOVALS", True)

    assert linguas.expected(["vi", "ach"])[1] == ["de", "en_ZA"]


def test_check_reports_without_writing(linguas, tmp_path, monkeypatch, capsys):
    (tmp_path / "LINGUAS").write_text("vi\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["update-linguas.py", "--check"])

    assert linguas.main() == 1
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "vi\n"
    assert "add de (50%)" in capsys.readouterr().out


def test_writes_linguas(linguas, tmp_path, monkeypatch):
    (tmp_path / "LINGUAS").write_text("vi\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["update-linguas.py"])

    assert linguas.main() == 0
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\nen_ZA\nvi\n"
