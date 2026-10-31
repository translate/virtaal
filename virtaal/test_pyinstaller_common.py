#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
from pathlib import Path

import pytest

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging")


@pytest.fixture
def common(monkeypatch):
    monkeypatch.syspath_prepend(PACKAGING_DIR)
    spec = importlib.util.spec_from_file_location("pyinstaller_common",
                                                  os.path.join(PACKAGING_DIR, "pyinstaller_common.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mo_files_land_in_share_locale(common, tmp_path):
    (tmp_path / "mo" / "de").mkdir(parents=True)
    (tmp_path / "mo" / "de" / "virtaal.mo").write_bytes(b"")

    assert common.mo_files(tmp_path) == [
        (str(tmp_path / "mo" / "de" / "virtaal.mo"), str(Path("share", "locale", "de", "LC_MESSAGES"))),
    ]


def test_datas_ship_virtaal_and_translate_data_and_authors(common, tmp_path):
    dests = [dest for _src, dest in common.datas(tmp_path)]

    assert dests == ["share/virtaal", "share/icons", "share", "."]
    assert (common.TRANSLATE_SHARE / "langmodels").is_dir()


def test_hiddenimports_skip_tests_and_enchant_dialogs(common):
    assert common.not_test("virtaal.views.textbox")
    assert not common.not_test("virtaal.views.test_textbox")
    assert not common.not_test("virtaal.conftest")
    assert common.not_enchant_dialog("enchant.checker")
    assert not common.not_enchant_dialog("enchant.checker.GtkSpellCheckerDialog")


def test_hooksconfig_adds_module_versions_and_gi_options(common):
    config = common.hooksconfig(["de"], module_versions={"GtkosxApplication": "1.0"}, icons=["hicolor"])

    assert config["gi"]["module-versions"] == {"Gtk": "3.0", "GtkosxApplication": "1.0"}
    assert "de" in config["gi"]["languages"]
    assert config["gi"]["icons"] == ["hicolor"]
    assert common.hooksconfig(["de"])["gi"]["module-versions"] == {"Gtk": "3.0"}


def test_trim_drops_unused_babel_data_and_catalogs(common, tmp_path):
    (tmp_path / "po").mkdir()
    (tmp_path / "po" / "de.po").write_text("")
    toc = [
        ("babel/locale-data/de.dat", "/src/de.dat", "DATA"),
        ("babel/locale-data/fr.dat", "/src/fr.dat", "DATA"),
        ("share/locale/de/LC_MESSAGES/atk10.mo", "/src/atk10.mo", "DATA"),
        ("share/locale/de/LC_MESSAGES/gtk30.mo", "/src/gtk30.mo", "DATA"),
    ]

    kept = [dest for dest, _src, _kind in common.trim(toc, tmp_path)]

    assert kept == ["babel/locale-data/de.dat", "share/locale/de/LC_MESSAGES/gtk30.mo"]


def test_check_catalogs_exits_on_another_copy_of_virtaals_catalog(common, tmp_path):
    mo = tmp_path / "virtaal.mo"
    mo.write_bytes(b"")
    mo_files = [(str(mo), "share/locale/de/LC_MESSAGES")]
    toc = [("share/locale/de/LC_MESSAGES/virtaal.mo", "/elsewhere/virtaal.mo", "DATA")]

    with pytest.raises(SystemExit, match="another copy"):
        common.check_catalogs(toc, mo_files, ["de"])
