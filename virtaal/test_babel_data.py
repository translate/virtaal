#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging")


def _babel_data():
    spec = importlib.util.spec_from_file_location("babel_data", os.path.join(PACKAGING_DIR, "babel_data.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ui_locale_names_include_each_languages_parents(tmp_path):
    for lang in ("pt_BR", "zh_CN", "sr@latin"):
        (tmp_path / (lang + ".po")).write_text("")

    names = _babel_data().ui_locale_names(str(tmp_path))

    assert {"pt_BR", "pt", "zh_Hans_CN", "zh_Hans", "zh", "sr_Latn", "root"} <= names
    assert "de" not in names


def test_trim_drops_only_unused_babel_locale_files(tmp_path):
    (tmp_path / "de.po").write_text("")
    datas = [
        ("babel/locale-data/de.dat", "/src/de.dat", "DATA"),
        ("babel/locale-data/root.dat", "/src/root.dat", "DATA"),
        ("babel/locale-data/fr.dat", "/src/fr.dat", "DATA"),
        ("babel/global.dat", "/src/global.dat", "DATA"),
        ("share/virtaal/virtaal.ui", "/src/virtaal.ui", "DATA"),
    ]

    kept = [dest for dest, _src, _kind in _babel_data().trim(datas, str(tmp_path))]

    assert kept == ["babel/locale-data/de.dat", "babel/locale-data/root.dat",
                    "babel/global.dat", "share/virtaal/virtaal.ui"]
