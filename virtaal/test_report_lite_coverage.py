#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "devsupport", "pseudo-translation", "report_lite_coverage.py")

TEMPLATE = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "Open"\nmsgstr ""\n\nmsgctxt "Stock label"\nmsgid "_Close"\nmsgstr ""\n\n'
            'msgid "byte"\nmsgid_plural "bytes"\nmsgstr[0] ""\nmsgstr[1] ""\n')


@pytest.fixture
def coverage(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("report_lite_coverage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lite = module._lite_module()
    po_dir, upstream = tmp_path / "po", tmp_path / "upstream"
    (po_dir / "lite" / "gtk30").mkdir(parents=True)
    (po_dir / "lite" / "gtk30" / "gtk30.pot").write_text(TEMPLATE, encoding="utf-8")
    (po_dir / "LINGUAS").write_text("af\nen_GB\npt_BR\nzu\n", encoding="utf-8")
    (po_dir / "LINGUAS-lite").write_text("gtk30/zu\niso_639/zu\n", encoding="utf-8")
    (po_dir / "virtaal.priorities.yaml").write_text(
        "domains:\n  gtk30:\n    '1': [Open]\n    1~: [\"Stock label\\x04_Close\", byte]\n"
        "  iso639-3:\n    '1': [English]\n", encoding="utf-8")
    # Upstream: pt covers everything (pt_BR falls back to it), af half.
    everything = {"Open": "Abrir", "Stock label\x04_Close": "_Fechar", "byte\0bytes": "byte\0bytes"}
    lite.write_mo(str(upstream / "pt" / "LC_MESSAGES" / "gtk30.mo"), everything)
    lite.write_mo(str(upstream / "af" / "LC_MESSAGES" / "gtk30.mo"), {"Open": "Maak oop"})
    lite.write_mo(str(upstream / "zu" / "LC_MESSAGES" / "gtk30.mo"), {"Open": "Vula"})
    # zu's lite catalog fills _Close, not byte.
    (po_dir / "lite" / "gtk30" / "zu.po").write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgctxt "Stock label"\nmsgid "_Close"\nmsgstr "_Vala"\n', encoding="utf-8")
    monkeypatch.setattr(module, "PO_DIR", str(po_dir))
    monkeypatch.setattr(module, "LITE_DIR", str(po_dir / "lite"))
    monkeypatch.setattr(lite, "LIBRARY_NAMESPACES", {"gtk30": "Gtk", "gtkspell3": "GtkSpell"})
    monkeypatch.setattr(lite, "library_locale_dir", lambda ns: str(upstream) if ns == "Gtk" else None)
    monkeypatch.setattr(module, "_name_translated", lambda lite, lang, name: lang != "af")
    return module, lite


def test_reports_what_neither_upstream_nor_shipped_lite_translates(coverage):
    module, lite = coverage

    report, skipped = module.missing(lite)

    assert report == {"gtk30": {"af": ["Stock label\x04_Close", "byte\0bytes"], "zu": ["byte\0bytes"]}}
    assert skipped == ["gtkspell3"]


def test_markdown_lists_each_language_and_message(coverage):
    module, lite = coverage

    summary, _, details = module.markdown(*module.missing(lite), "macOS (Homebrew)").partition("<details>")

    assert "| GTK (3 strings) | af (2 strings), zu (1) |" in summary
    assert "| gtkspell | not on this build host, so not shipped |" in summary
    assert "| af | 2 | `_Close (Stock label)`, `byte` |" in details


def test_main_warns_once_and_writes_the_job_summary(coverage, tmp_path, monkeypatch, capsys):
    module, lite = coverage
    monkeypatch.setattr(module, "_lite_module", lambda: lite)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    assert module.main(["--host", "Windows (gvsbuild)"]) == 0

    out = capsys.readouterr().out
    assert out.count("::warning") == 1
    assert "::warning title=Lite coverage gaps (Windows (gvsbuild))::" in out
    assert "2 shipped language(s) show 3 library message(s)" in out
    assert "## Lite coverage - Windows (gvsbuild)" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_main_stays_quiet_outside_github_actions(coverage, monkeypatch, capsys):
    module, lite = coverage
    monkeypatch.setattr(module, "_lite_module", lambda: lite)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert module.main(["--host", "Windows (gvsbuild)"]) == 0

    assert "::warning" not in capsys.readouterr().out


def test_level_one_gaps_count_core_and_rest_with_language_names(coverage):
    module, lite = coverage

    # af: _Close and byte (rest), English (core); zu: byte; pt_BR nothing.
    assert module.level_one_gaps(lite) == {"af": (1, 2), "zu": (0, 1)}


def test_markdown_leads_with_the_level_one_gaps(coverage):
    module, lite = coverage
    report, skipped = module.missing(lite)

    text = module.markdown(report, skipped, "macOS (Homebrew)", module.level_one_gaps(lite, report))

    assert "Level 1 (the release rule, `po/update-linguas.py --cut-off`): af (3 strings), zu (1)." in text
