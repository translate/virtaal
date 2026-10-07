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
    (tmp_path / "virtaal.pot").write_text(TEMPLATE, encoding="utf-8")
    (tmp_path / "de.po").write_text(_po(One="Eins", Two="Zwei"), encoding="utf-8")
    (tmp_path / "vi.po").write_text(_po(One="Một", Two=None), encoding="utf-8")
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

    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\nen_ZA\nvi\n"


def test_check_reports_without_writing(linguas, tmp_path, monkeypatch, capsys):
    assert _run(linguas, monkeypatch, "--check") == 1

    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\n"
    assert "add vi" in capsys.readouterr().out


@needs_gettext
def test_coverage_counts_translated_messages_not_fuzzy_ones(linguas):
    assert linguas.below_threshold(["ach", "de", "en_ZA", "vi"]) == {"vi": 25}


@needs_gettext
def test_standing_counts_strings_over_or_under_the_threshold(linguas):
    assert linguas.standing(["de", "en_ZA", "vi"]) == ({"de": 0, "vi": -1}, 4)


@needs_gettext
def test_report_calls_out_who_could_make_it_and_who_could_slip(linguas, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    assert _run(linguas, monkeypatch, "--report") == 0

    out = capsys.readouterr().out
    summary, _, details = out.partition("<details>")
    assert "| Could make it | vi (1 string needed) |" in summary
    assert "| Could slip | de (0 to spare) |" in summary
    assert "| Further off | - |" in summary
    assert "| de | 50% | +0 | could slip |" in details
    assert "ach" not in out
    assert "## Release threshold" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\n"


@needs_gettext
def test_cut_off_excludes_below_threshold_with_coverage_as_reason(linguas, tmp_path, monkeypatch):
    assert _run(linguas, monkeypatch, "--cut-off", "1.0.0") == 0

    assert linguas.excluded() == {"ach": "reasons", "vi": "below 50% at 1.0.0 (25%)"}
    assert (tmp_path / "LINGUAS").read_text(encoding="utf-8") == "de\nen_ZA\n"
