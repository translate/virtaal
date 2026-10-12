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

IMPORTS = {
    "libenchant-2.dll": ["libglib-2.0-0.dll", "KERNEL32.dll"],
    "enchant_hunspell.dll": ["libenchant-2.dll", "libhunspell-1.7-0.dll"],
    "enchant_nuspell.dll": ["libenchant-2.dll", "libicuuc72.dll"],
    "libglib-2.0-0.dll": ["libintl-8.dll"],
    "libhunspell-1.7-0.dll": ["libstdc++-6.dll"],
    "libintl-8.dll": [],
    "libstdc++-6.dll": [],
    "libicuuc72.dll": [],
    "tcl86.dll": [],
}


def _enchant_data():
    spec = importlib.util.spec_from_file_location("enchant_data", os.path.join(PACKAGING_DIR, "enchant_data.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mingw(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "lib" / "enchant-2").mkdir(parents=True)
    for name in IMPORTS:
        folder = "lib/enchant-2" if name.startswith("enchant_") else "bin"
        (tmp_path / folder / name).write_bytes(b"")
    return tmp_path


def _imports(path):
    return IMPORTS[path.name]


def test_needed_dlls_follows_imports_from_enchant_and_the_bundled_backends(tmp_path):
    needed = _enchant_data().needed_dlls(_mingw(tmp_path), _imports)

    assert needed == {"libenchant-2.dll", "libglib-2.0-0.dll", "libintl-8.dll",
                      "libhunspell-1.7-0.dll", "libstdc++-6.dll"}


def test_trim_drops_other_backends_unloaded_dlls_and_static_libraries(tmp_path):
    bin_dir = os.path.join("enchant", "data", "mingw64", "bin")
    lib_dir = os.path.join("enchant", "data", "mingw64", "lib", "enchant-2")
    toc = [
        (os.path.join(bin_dir, "libenchant-2.dll"), "/src", "BINARY"),
        (os.path.join(bin_dir, "libintl-8.dll"), "/src", "BINARY"),
        (os.path.join(bin_dir, "tcl86.dll"), "/src", "BINARY"),
        (os.path.join(lib_dir, "enchant_hunspell.dll"), "/src", "BINARY"),
        (os.path.join(lib_dir, "enchant_nuspell.dll"), "/src", "BINARY"),
        (os.path.join(bin_dir, "libicuuc72.dll"), "/src", "BINARY"),
        (os.path.join(lib_dir, "enchant_hunspell.a"), "/src", "DATA"),
        (os.path.join(lib_dir, "enchant_hunspell.dll.a"), "/src", "DATA"),
        (os.path.join(lib_dir, "enchant_hunspell.la"), "/src", "DATA"),
        (os.path.join("enchant", "data", "mingw64", "share", "enchant", "hunspell", "en_GB.dic"), "/src", "DATA"),
        ("tcl86.dll", "/src", "BINARY"),
    ]

    trimmed = _enchant_data().trim(toc, _mingw(tmp_path), _imports)

    assert [os.path.basename(entry[0]) for entry in trimmed] == [
        "libenchant-2.dll", "libintl-8.dll", "enchant_hunspell.dll", "en_GB.dic", "tcl86.dll"]
