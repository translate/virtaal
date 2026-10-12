#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Trims pyenchant's Windows wheel in a frozen build to the DLLs its
spelling backends load. The wheel ships a whole MSYS2 mingw64 tree,
mostly other programs' DLLs plus static libraries."""

from pathlib import Path

ENCHANT_DLL = "libenchant-2.dll"
BACKENDS = ("enchant_hunspell.dll",)


def pe_imports(path):
    """The DLL names a Windows binary imports."""
    import pefile

    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    return [entry.dll.decode() for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]


def needed_dlls(mingw_dir, imports=pe_imports):
    """Lower-cased names of the DLLs in mingw_dir/bin that libenchant
        and the bundled backends load, directly or not."""
    mingw_dir = Path(mingw_dir)
    available = {p.name.lower(): p for p in (mingw_dir / "bin").glob("*.dll")}
    needed = {ENCHANT_DLL}
    todo = [mingw_dir / "bin" / ENCHANT_DLL] + [mingw_dir / "lib" / "enchant-2" / name for name in BACKENDS]
    while todo:
        for name in imports(todo.pop()):
            name = name.lower()
            if name in available and name not in needed:
                needed.add(name)
                todo.append(available[name])
    return needed


def trim(toc, mingw_dir, imports=pe_imports):
    """PyInstaller binaries or datas without the enchant backends not
        bundled, the DLLs nothing loads and the static libraries."""
    keep = needed_dlls(mingw_dir, imports)
    trimmed = []
    for entry in toc:
        dest = Path(entry[0])
        if dest.parts[:3] == ("enchant", "data", "mingw64"):
            if dest.suffix in (".a", ".la"):
                continue
            if dest.parent.name == "bin" and dest.suffix.lower() == ".dll" and dest.name.lower() not in keep:
                continue
            if dest.parent.name == "enchant-2" and dest.name not in BACKENDS:
                continue
        trimmed.append(entry)
    return trimmed
