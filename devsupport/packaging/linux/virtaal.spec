# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Linux AppImage. Run via build_appimage.sh.
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(os.getcwd())

sys.path.insert(0, str(ROOT))
from virtaal.support.libi18n.lite import (  # noqa: E402
    bundle_languages, expected_catalogs, is_unused_catalog, missing_catalogs, mismatched_catalogs,
    read_linguas,
)

sys.path.insert(0, str(ROOT / "devsupport" / "packaging"))
import babel_data  # noqa: E402

# translate-toolkit's own data (langmodels/, stoplist-en), which
# translate.misc.file_discovery looks for under share/ when frozen.
import translate  # noqa: E402
TRANSLATE_SHARE = Path(translate.__file__).parent / "share"

LANGUAGES = read_linguas(ROOT / "po" / "LINGUAS")

ARCH_LIBDIR = Path("/usr/lib") / subprocess.run(
    ["gcc", "-print-multiarch"], capture_output=True, text=True, check=True,
).stdout.strip()


def _required(path):
    if not path.exists():
        raise SystemExit("Not found (see build_appimage.sh for the packages): %s" % path)
    return path


mo_files = [
    (str(p), str(Path("share", "locale") / p.relative_to(ROOT / "mo").parent / "LC_MESSAGES"))
    for p in (ROOT / "mo").rglob("*.mo")
]

# libgettextpo, for the msgfmt check (virtaal/support/gettextpo.py).
# Loaded with ctypes, so nothing else pulls it in.
GETTEXTPO = _required(ARCH_LIBDIR / "libgettextpo.so.0")

# The relocatable enchant build_appimage.sh builds, and its hunspell
# provider. pyi_rth_appimage.py points pyenchant at
# enchant/lib/libenchant-2.so.2 (a link to the bundled library), which
# makes enchant look for the provider in enchant/lib/enchant-2/. The
# provider still finds the host's dictionaries (XDG_DATA_DIRS/hunspell).
ENCHANT_PREFIX = Path(os.environ["VIRTAAL_ENCHANT_PREFIX"])
ENCHANT_LIBRARY = _required(ENCHANT_PREFIX / "lib" / "libenchant-2.so.2")
ENCHANT_HUNSPELL = _required(ENCHANT_PREFIX / "lib" / "enchant-2" / "enchant_hunspell.so")

# Input methods: GTK's own (IBus, XIM, Wayland, ...) and Fcitx 5's.
# GTK_IM_MODULE_FILE points GTK at the cache written below.
IMMODULES_DIR = _required(ARCH_LIBDIR / "gtk-3.0" / "3.0.0" / "immodules")
IMMODULES = sorted(IMMODULES_DIR.glob("im-*.so"))
for _name in ("im-ibus.so", "im-fcitx5.so", "im-wayland.so", "im-xim.so"):
    _required(IMMODULES_DIR / _name)
IMMODULES_DEST = "lib/gtk-3.0/3.0.0/immodules"
IMMODULES_CACHE = ROOT / "build" / "appimage" / "immodules.cache.in"
IMMODULES_CACHE.parent.mkdir(parents=True, exist_ok=True)
IMMODULES_CACHE.write_text(subprocess.run(
    [str(_required(ARCH_LIBDIR / "libgtk-3-0" / "gtk-query-immodules-3.0"))] + [str(p) for p in IMMODULES],
    capture_output=True, text=True, check=True,
).stdout.replace(str(IMMODULES_DIR), "@BUNDLE@/" + IMMODULES_DEST), encoding="utf-8")

# Adwaita, as a run from source has, for hosts without GNOME's icons.
# Ubuntu 22.04's has its symbolic icons in scalable/ and 16x16/. Not its
# cursors: GTK uses the host's.
ADWAITA = Path("/usr/share/icons/Adwaita")
ADWAITA_PARTS = ["index.theme", "scalable", "scalable-up-to-32", "16x16"]
for _part in ADWAITA_PARTS:
    _required(ADWAITA / _part)

datas = [
    (str(ROOT / "share" / "virtaal"), "share/virtaal"),
    (str(ROOT / "share" / "icons"), "share/icons"),
    (str(TRANSLATE_SHARE), "share"),
    # virtaal/support/authors.py reads this at the bundle root.
    (str(ROOT / "AUTHORS.md"), "."),
    (str(IMMODULES_CACHE), "lib/gtk-3.0/3.0.0"),
]
datas += [
    (str(ADWAITA / part), "share/icons/Adwaita" if part == "index.theme" else "share/icons/Adwaita/" + part)
    for part in ADWAITA_PARTS
]
datas += mo_files


# lxml modules nothing imports; PyInstaller's lxml hook collects them all.
UNUSED_LXML = [
    "lxml.objectify", "lxml.sax", "lxml.builder", "lxml.html.builder", "lxml.html.diff",
    "lxml.html._difflib", "lxml.html._diffcommand", "lxml.isoschematron",
]


def _not_test(name):
    leaf = name.rpartition(".")[2]
    return not (leaf.startswith("test_") or leaf == "conftest")


def _not_enchant_dialog(name):
    return name not in (
        "enchant.checker.CmdLineChecker",
        "enchant.checker.GtkSpellCheckerDialog",
        "enchant.checker.wxSpellCheckerDialog",
    )


a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=(
        [(str(GETTEXTPO), "."), (str(ENCHANT_HUNSPELL), "enchant/lib/enchant-2")]
        + [(str(path), IMMODULES_DEST) for path in IMMODULES]
    ),
    datas=datas,
    hiddenimports=(
        collect_submodules("virtaal", filter=_not_test)
        + collect_submodules("translate.storage")
        + collect_submodules("enchant", filter=_not_enchant_dialog)
    ),
    hooksconfig={
        "gi": {
            "module-versions": {
                "Gtk": "3.0",
                "GtkSpell": "3.0",
            },
            "languages": bundle_languages(LANGUAGES),
            # Adwaita is bundled above.
            "icons": ["hicolor"],
            "themes": ["Adwaita"],
        },
    },
    hookspath=[str(ROOT / "devsupport" / "packaging" / "linux" / "pyinstaller-hooks")],
    runtime_hooks=[str(ROOT / "devsupport" / "packaging" / "linux" / "pyi_rth_appimage.py")],
    excludes=["FixTk", "tcl", "tk", "_tkinter", "tkinter", "Tkinter", "devsupport"] + UNUSED_LXML,
    noarchive=False,
)
a.datas = babel_data.trim(a.datas, str(ROOT / "po"))
# The host's: they read the host's own font configuration, which can be
# newer than this build's (AppImage's own exclude list leaves them out too).
HOST_LIBRARIES = ("libfontconfig.so.1", "libfreetype.so.6")
a.binaries = [entry for entry in a.binaries if os.path.basename(entry[0]) not in HOST_LIBRARIES]
a.datas = [entry for entry in a.datas if not is_unused_catalog(entry[0])]

# GTK's own schemas only. PyInstaller compiles every schema on the build
# machine, and the bundle's share/ comes first in XDG_DATA_DIRS: its
# org.gnome.desktop.interface hid the host's defaults (Ubuntu's Yaru
# icons, under Wayland).
SCHEMAS = ROOT / "build" / "appimage" / "schemas"
shutil.rmtree(SCHEMAS, ignore_errors=True)
SCHEMAS.mkdir(parents=True)
for _schema in Path("/usr/share/glib-2.0/schemas").glob("org.gtk.Settings.*.gschema.xml"):
    shutil.copy(_schema, SCHEMAS)
subprocess.run([str(_required(ARCH_LIBDIR / "glib-2.0" / "glib-compile-schemas")), str(SCHEMAS)], check=True)
_compiled = "share/glib-2.0/schemas/gschemas.compiled"
if not any(dest == _compiled for dest, _src, _kind in a.datas):
    raise SystemExit("PyInstaller bundled no %s" % _compiled)
a.datas = [(dest, str(SCHEMAS / "gschemas.compiled") if dest == _compiled else src, kind)
           for dest, src, kind in a.datas]

# gtkspell3's enchant must be the relocatable one, not Ubuntu's.
_enchant_sources = [src for dest, src, _kind in a.binaries if dest == "libenchant-2.so.2"]
if [os.path.realpath(src) for src in _enchant_sources] != [os.path.realpath(ENCHANT_LIBRARY)]:
    raise SystemExit("Bundled the wrong enchant: %r" % _enchant_sources)
# The Toolkit's spelling check imports enchant.checker.
if "enchant.checker" not in {entry[0] for entry in a.pure}:
    raise SystemExit("enchant.checker isn't bundled")
# The spell checker plugin needs GtkSpell's typelib.
if not any(dest.endswith("GtkSpell-3.0.typelib") for dest, _src, _kind in a.datas + a.binaries):
    raise SystemExit("GtkSpell-3.0.typelib isn't bundled")

# PyInstaller keeps the first datas entry for a destination: our merged
# lite catalogs, listed in datas above, must beat the copies GTK's and
# GLib's own hooks collect at the same path.
_mismatched = mismatched_catalogs(a.datas, mo_files)
if _mismatched:
    raise SystemExit("Bundled another copy instead of Virtaal's catalog: %r" % _mismatched)
_missing = missing_catalogs(a.datas, expected_catalogs(LANGUAGES, mo_files))
if _missing:
    raise SystemExit("Shipped languages missing catalogs: %r" % _missing)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    exclude_binaries=True,
    # Not "virtaal": in the flat layout, an executable of that name next
    # to the bundled modules stops "import virtaal.cli" finding the package.
    name="Virtaal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    # The flat layout: translate-toolkit's frozen data lookup expects
    # share/ next to the executable (see the Windows spec).
    contents_directory=".",
)

coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="virtaal"
)
