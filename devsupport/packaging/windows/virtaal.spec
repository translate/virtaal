# Run PyInstaller with this spec from the repo root:
#   pyinstaller -y devsupport/packaging/windows/virtaal.spec
# (or via devsupport/packaging/windows/build_standalone.ps1, which also
# handles the mo-compile prerequisite - see that script's header for why
# this exists alongside a plain pip install rather than replacing it.)
#
# Modeled on gaphor/gaphor's real, current, shipping PyInstaller spec.
# collect_submodules across the whole virtaal package is needed for two
# dynamic-import points PyInstaller's static analysis can't see on its
# own: virtaal's own directory-scanning plugin loader in
# plugincontroller.py, and virtaal/support/tmserver.py, only ever
# reached via bin/virtaal's own runpy-based "--run-module" dispatch -
# see localtm.py.
#
# Same reasoning covers translate.storage: factory.getobject() imports
# a format's backend module by a runtime-computed string, invisible to
# PyInstaller unless collected explicitly too.
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

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo,
)

ROOT = Path(os.getcwd())

sys.path.insert(0, str(ROOT))
from virtaal.__version__ import ver as virtaal_version  # noqa: E402

# translate-toolkit ships its own small data directory (translate/share/ -
# langmodels/, the ngram language-model files translate.lang.identify.
# LanguageIdentifier needs for auto-detection, plus stoplist-en) that
# translate.misc.file_discovery's frozen-mode lookup expects to find at
# <exe_dir>/share/<name>, same flat layout as virtaal's own share/virtaal
# and share/icons below - it's a third-party package's data, not
# virtaal's own, so it was never in this datas list at all. Confirmed
# live, 2026-08-24: clicking the language-pair selector (which triggers
# get_detected_langs(), langcontroller.py) crashed with
# ValueError: Could not find "langmodels" - the only UI path that reaches
# this particular translate-toolkit feature, so it went unnoticed until
# a Windows UI-testing battery specifically exercised that click. Located
# dynamically (not a hardcoded venv path) via the actually-imported
# translate module, same style as everything else in this file.
import translate  # noqa: E402
TRANSLATE_SHARE = Path(translate.__file__).parent / "share"

COPYRIGHT = "Copyright 2007-2026 Translate. GNU General Public License."


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
                StringStruct('LegalCopyright', COPYRIGHT),
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

mo_files = [
    (str(p), str(Path("share", "locale") / p.relative_to(ROOT / "mo").parent / "LC_MESSAGES"))
    for p in (ROOT / "mo").rglob("*.mo")
]

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

a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=[
        (str(ROOT / "share" / "virtaal"), "share/virtaal"),
        (str(ROOT / "share" / "icons"), "share/icons"),
        (str(TRANSLATE_SHARE), "share"),
    ]
    + mo_files,
    hiddenimports=collect_submodules("virtaal") + collect_submodules("translate.storage"),
    hooksconfig={
        "gi": {
            "module-versions": {
                "Gtk": "3.0",
            },
        },
    },
    # devsupport isn't needed at runtime in a frozen build (its one
    # consumer, profiling support, is already `if not packaged:`-gated
    # off in bin/virtaal itself). Excluding it also avoids a real bug
    # found during frozen-build testing: a vendored Python-2-era
    # "Optik" optparse.py inside devsupport/ was shadowing the real
    # stdlib module for bin/virtaal's bare `import optparse` (since
    # deleted from the repo entirely, but excluding the whole directory
    # is belt-and-suspenders regardless, and costs nothing since it's
    # dead weight here either way).
    excludes=[
        "FixTk", "tcl", "tk", "_tkinter", "tkinter", "Tkinter", "devsupport",
        # pyenchant loads the SYSTEM libenchant via ctypes at runtime, not
        # a static import PyInstaller's analysis can see - never bundled
        # regardless of whether it's excluded here. The pinned gvsbuild
        # GTK3 build this project uses doesn't ship enchant/gtkspell at
        # all (confirmed live in the Windows 11 ARM64 VM this session -
        # "GtkSpell not installed"), so the spellchecker plugin already
        # degrades gracefully without it, same as a plain checkout
        # running without enchant/gtkspell installed locally.
        "enchant",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="virtaal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
)

coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="virtaal"
)
