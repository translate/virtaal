# Run PyInstaller with this spec from the repo root:
#   pyinstaller -y devsupport/packaging/windows/virtaal.spec
# (or via devsupport/packaging/windows/build_standalone.ps1, which also
# handles the mo-compile prerequisite - see that script's header for why
# this exists alongside a plain pip install rather than replacing it.)
#
# The parts shared with the macOS spec are in
# devsupport/packaging/pyinstaller_common.py.
#
# --onedir (not --onefile): translate.misc.file_discovery's frozen-mode
# data lookup (os.path.dirname(sys.executable), confirmed by reading the
# installed package directly) assumes a flat, same-directory-as-
# executable layout - exactly what PyInstaller's default Windows
# --onedir output already is. --onefile self-extracts to a temp
# directory on every launch instead, which would move data files
# somewhere unpredictable and defeat that assumption.
import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)

ROOT = Path(os.getcwd())

sys.path.insert(0, str(ROOT))
from virtaal.__version__ import ver as virtaal_version  # noqa: E402

sys.path.insert(0, str(ROOT / "devsupport" / "packaging"))
import enchant_data  # noqa: E402
import pyinstaller_common as common  # noqa: E402

# pyenchant's Windows wheel is self-contained (libenchant + backends +
# English dictionaries under enchant/data/); _enchant.py finds it via
# its own __file__ at runtime, so bundling the dir at the same relative
# path is enough - see module_collection_mode below.
try:
    import enchant
    ENCHANT_DATA = Path(enchant.__file__).parent / "data"
except ImportError:
    ENCHANT_DATA = None


def _version_tuple(ver):
    """VSVersionInfo needs a plain 4-int tuple - ver is e.g. "1.0.0-beta1",
        so take the numeric release part only and pad/truncate to 4."""
    nums = [int(n) for n in re.findall(r'\d+', ver.split('-')[0])][:4]
    return tuple(nums + [0] * (4 - len(nums)))


_ver_tuple = _version_tuple(virtaal_version)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_ver_tuple,
        prodvers=_ver_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x4,       # VOS_NT_WINDOWS32
        fileType=0x1,  # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable('040904B0', [
                StringStruct('CompanyName', 'Translate'),
                StringStruct('FileDescription', 'Virtaal'),
                StringStruct('FileVersion', virtaal_version),
                StringStruct('InternalName', 'virtaal'),
                StringStruct('LegalCopyright', common.COPYRIGHT),
                StringStruct('OriginalFilename', 'virtaal.exe'),
                StringStruct('ProductName', 'Virtaal'),
                StringStruct('ProductVersion', virtaal_version),
            ]),
        ]),
        # 1033 = LANG_ENGLISH/SUBLANG_ENGLISH_US, 1200 = Unicode codepage -
        # must match the StringTable's own '040904B0' (same two values,
        # hex-encoded) or Explorer's Properties dialog won't show the
        # strings above at all.
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),
    ],
)

LANGUAGES = common.languages(ROOT)
mo_files = common.mo_files(ROOT)

# gvsbuild's own GTK3 install, from ci.yml's "Download prebuilt GTK3
# (gvsbuild)" step (always C:\gtk - same convention the env vars there
# use). PyInstaller's own build log for this spec warned "Could not
# determine Gio modules path! / Bundling Gio modules is not supported on
# your platform." - GIO modules cover things like network-monitor/D-Bus
# backends, and a GTK app failing to find them is a known way for one to
# hang (retrying a backend connection) rather than fail cleanly. Bundle
# gvsbuild's own gio/modules directory explicitly rather than relying on
# PyInstaller's own (apparently absent-on-this-platform) GIO-module
# discovery. Guarded on the directory actually existing rather than a
# hard path reference, in case a future gvsbuild layout changes this -
# better to build without it (and re-hit the same warning) than hard-fail
# the whole build over one optional directory.
GTK_ROOT = Path(r"C:\gtk")
gio_modules_dir = GTK_ROOT / "lib" / "gio" / "modules"
binaries = []
if gio_modules_dir.is_dir():
    binaries.append((str(gio_modules_dir), "lib/gio/modules"))
# libgettextpo, for the msgfmt check (virtaal/support/gettextpo.py). Loaded
# with ctypes, so nothing else pulls it in.
GETTEXTPO = GTK_ROOT / "bin" / "gettextpo.dll"
if not GETTEXTPO.is_file():
    raise SystemExit("libgettextpo not found: %s" % GETTEXTPO)
binaries.append((str(GETTEXTPO), "."))

datas = common.datas(ROOT) + mo_files
if ENCHANT_DATA is not None and ENCHANT_DATA.is_dir():
    # Only en_US (the traditional software source language) and en_GB
    # (checks.po's own target language, exercised by ci.yml's bundle-
    # launch check) - the rest comes via download, not bundled (~20MB
    # of unused dictionaries otherwise).
    BUNDLED_DICTS = ("en_US", "en_GB")
    for p in ENCHANT_DATA.rglob("*"):
        if p.is_dir():
            continue
        if p.parent.name == "hunspell" and p.stem not in BUNDLED_DICTS:
            continue
        datas.append((str(p), str(Path("enchant/data") / p.relative_to(ENCHANT_DATA).parent)))

a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    # Overrides pyinstaller-hooks-contrib's own hook-enchant.py, which
    # bundles every dictionary in the wheel regardless of the en_GB
    # filtering above - see that file's own docstring.
    hookspath=[str(ROOT / "devsupport" / "packaging" / "windows" / "pyinstaller-hooks")],
    hiddenimports=common.hiddenimports(),
    # Keep enchant's .py files loose on disk, not archived - its
    # __file__-relative data lookup above needs a real path.
    module_collection_mode={"enchant": "py"},
    hooksconfig=common.hooksconfig(LANGUAGES),
    excludes=common.EXCLUDES,
    noarchive=False,
)
a.datas = common.trim(a.datas, ROOT)
if ENCHANT_DATA is not None and ENCHANT_DATA.is_dir():
    a.binaries = enchant_data.trim(a.binaries, ENCHANT_DATA / "mingw64")
    a.datas = enchant_data.trim(a.datas, ENCHANT_DATA / "mingw64")

# The Toolkit's spelling check imports enchant.checker.
if not any(Path(entry[0]) == Path("enchant", "checker", "__init__.py") for entry in a.datas):
    raise SystemExit("enchant.checker isn't bundled")

common.check_catalogs(a.datas, mo_files, LANGUAGES)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    icon=str(ROOT / "share" / "icons" / "virtaal.ico"),
    version=version_info,
    # PyInstaller 6.0 changed --onedir's default layout to collect
    # everything (including `datas`, e.g. share/virtaal/virtaal.ui) into
    # a _internal/ subdirectory instead of flat next to the exe.
    # Confirmed live: translate-toolkit's file_discovery.py (third-party,
    # not ours to edit) has its own frozen-mode data lookup that assumes
    # the pre-6.0 flat layout (os.path.dirname(sys.executable) + "share"
    # directly, no _internal/ level) - crashed with `ValueError: Could
    # not find "virtaal\virtaal.ui"` because the actual bundled location
    # was C:\...\dist\virtaal\_internal\share\virtaal\virtaal.ui, one
    # level off from where it looked. contents_directory="." is
    # PyInstaller's own documented way to opt back into the flat layout.
    contents_directory=".",
    **common.EXE_OPTIONS,
)

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, **common.COLLECT_OPTIONS)  # noqa: F821
