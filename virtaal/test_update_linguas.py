#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import json
import os
import shutil

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "po", "update-linguas.py")

TEMPLATE = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "One"\nmsgstr ""\n\nmsgid "Two"\nmsgstr ""\n\n'
            'msgid "Three"\nmsgstr ""\n\nmsgid "Four"\nmsgstr ""\n')

needs_gettext = pytest.mark.skipif(not shutil.which("msgmerge"), reason="needs gettext's msgmerge")


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
    monkeypatch.setattr(module, "EXCLUDED", tmp_path / "LINGUAS-excluded")
    monkeypatch.setattr(module, "TEMPLATE", tmp_path / "virtaal.pot")
    monkeypatch.setattr(module, "PRIORITIES", tmp_path / "virtaal.priorities.yaml")
    monkeypatch.setattr(module, "LEVEL_ONE_TOLERANCE", 1)
    monkeypatch.setattr(module, "library_gaps", lambda: {})
    (tmp_path / "virtaal.priorities.yaml").write_text(
        "domains:\n  virtaal:\n    '1': [One]\n    1~: [Two, Three, Gone]\n", encoding="utf-8")
    (tmp_path / "virtaal.pot").write_text(TEMPLATE, encoding="utf-8")
    (tmp_path / "de.po").write_text(_po(One="Eins", Two="Zwei"), encoding="utf-8")
    (tmp_path / "vi.po").write_text(_po(One="Một", Two=None), encoding="utf-8")
    (tmp_path / "fr.po").write_text(_po(Two="Deux", Three="Trois", Four="Quatre"), encoding="utf-8")
    (tmp_path / "ach.po").write_text(_po(One="a", Two="b", Three="c", Four="d"), encoding="utf-8")
    (tmp_path / "en_ZA.po").write_text(_po(), encoding="utf-8")
    (tmp_path / "LINGUAS-excluded").write_text("# header\nach  # reasons\n", encoding="utf-8")
    (tmp_path / "LINGUAS").write_text("de\n", encoding="utf-8")
    return module


def _run(module, monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["update-linguas.py", *args])
    return module.main()


def test_reads_exclusions_and_their_reasons(linguas):
    assert linguas.excluded() == {"ach": "reasons"}


def test_ships_every_catalog_not_excluded(linguas, tmp_path, monkeypatch):
    assert _run(linguas, monkeypatch) == 0

    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\nen_ZA\nfr\nvi\n"


def test_check_reports_without_writing(linguas, tmp_path, monkeypatch, capsys):
    assert _run(linguas, monkeypatch, "--check") == 1

    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\n"
    assert "add vi" in capsys.readouterr().out


@needs_gettext
def test_translated_messages_leave_out_fuzzy_ones(linguas, tmp_path):
    assert linguas.translated_keys(tmp_path / "vi.po") == {"One"}


@needs_gettext
def test_standing_counts_strings_over_or_under_the_threshold(linguas):
    assert linguas.standing(["de", "en_ZA", "vi"]) == ({"de": 0, "vi": -1}, 4)


@needs_gettext
def test_level_one_leaves_out_messages_no_longer_in_the_template(linguas):
    assert linguas.level_one() == ({"One"}, {"Two", "Three"})


@needs_gettext
def test_readiness_counts_level_one_strings_missing_and_the_threshold_margin(linguas):
    assert linguas.readiness(["de", "en_ZA", "fr", "vi"]) == {"de": (0, 1, 0), "fr": (1, 0, 1), "vi": (0, 2, -1)}


@pytest.mark.parametrize("state, version, expected", [
    ((0, 1, 0), "1.1.0", "level 1"),
    # 50% ships one missing a core string, but only before 1.1.0.
    ((1, 0, 1), "1.0.0", "50%"),
    ((1, 0, 1), "1.1.0", None),
    ((0, 2, -1), "1.0.0", None),
])
def test_which_rule_ships_a_translation(linguas, state, version, expected):
    assert linguas.ships(state, version) == expected


@needs_gettext
def test_report_groups_translations_by_the_rule_that_ships_them(linguas, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    assert _run(linguas, monkeypatch, "--report") == 0

    out = capsys.readouterr().out
    summary, _, details = out.partition("<details>")
    assert "| Level 1 | de |" in summary
    assert "| 50% only, until 1.1.0 | fr (1 level-1 string needed) |" in summary
    assert "| Could make level 1 | vi (1 string needed) |" in summary
    assert "| fr | 1 | 0 | 1 | +1 | 50% only |" in details
    assert "| ach |" not in out and "ach (" not in out
    assert "## Release readiness" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\n"


@needs_gettext
def test_cut_off_excludes_what_the_release_rule_doesnt_ship(linguas, tmp_path, monkeypatch):
    assert _run(linguas, monkeypatch, "--cut-off", "1.0.0") == 0

    assert linguas.excluded() == {"ach": "reasons", "vi": "level 1 incomplete at 1.0.0 (0 core, 2 other strings missing)"}
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\nen_ZA\nfr\n"


@needs_gettext
def test_from_1_1_0_only_level_1_ships(linguas, tmp_path, monkeypatch):
    assert _run(linguas, monkeypatch, "--cut-off", "1.1.0") == 0

    assert set(linguas.excluded()) == {"ach", "fr", "vi"}


@needs_gettext
def test_cut_off_counts_the_libraries_level_one_too(linguas, tmp_path, monkeypatch):
    # de has all of Virtaal's level 1, but GTK on this host shows a core
    # message of it in English.
    monkeypatch.setattr(linguas, "library_gaps", lambda: {"de": (1, 0)})

    assert _run(linguas, monkeypatch, "--cut-off", "1.1.0") == 0

    assert linguas.excluded()["de"] == "level 1 incomplete at 1.1.0 (1 core, 1 other strings missing)"


@needs_gettext
def test_progress_writes_each_translations_standing(linguas, tmp_path, monkeypatch):
    (tmp_path / "virtaal.priorities.yaml").write_text(
        "domains:\n  virtaal:\n    '1': [One]\n    1~: [Two, Three]\n    '2': [Four]\n"
        "  gtk30:\n    '1': [_Open]\n", encoding="utf-8")
    monkeypatch.setattr(linguas, "library_gaps", lambda: {"de": (1, 0)})

    assert _run(linguas, monkeypatch, "--progress", str(tmp_path / "progress.json")) == 0

    data = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert data["totals"] == {"core": 2, "rest": 2, "level2": 1, "level3": 0}
    languages = {lang["code"]: lang for lang in data["languages"]}
    assert set(languages) == {"de", "fr", "vi"}
    assert languages["de"] == {
        "code": "de", "name": "German", "endonym": "Deutsch",
        "core_missing": 1, "rest_missing": 1, "needed": 1,
        "level2_missing": 1, "level3_missing": 0, "ships": "50%",
    }
    assert (languages["fr"]["core_missing"], languages["fr"]["ships"]) == (1, "50%")


@pytest.mark.parametrize("lang, names", [
    ("pt_BR", ("Portuguese (Brazil)", "português (Brasil)")),
    ("sr@latin", ("Serbian (Latin)", "srpski (latinica)")),
    ("son", ("Songhai languages", "Songhai languages")),
    ("xqz", ("xqz", "xqz")),
])
def test_names_come_from_cldr_then_iso_639(linguas, lang, names):
    assert linguas._names(lang) == names
