# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Linux AppImage. Run via build_appimage.sh.
# The parts shared with the other specs are in
# devsupport/packaging/pyinstaller_common.py.
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.getcwd())

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "devsupport" / "packaging"))
import pyinstaller_common as common  # noqa: E402

LANGUAGES = common.languages(ROOT)

ARCH_LIBDIR = Path("/usr/lib") / subprocess.run(
    ["gcc", "-print-multiarch"], capture_output=True, text=True, check=True,
).stdout.strip()


def _required(path):
    if not path.exists():
        raise SystemExit("Not found (see build_appimage.sh for the packages): %s" % path)
    return path


mo_files = common.mo_files(ROOT)

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

datas = common.datas(ROOT) + [(str(IMMODULES_CACHE), "lib/gtk-3.0/3.0.0")]
datas += [
    (str(ADWAITA / part), "share/icons/Adwaita" if part == "index.theme" else "share/icons/Adwaita/" + part)
    for part in ADWAITA_PARTS
]
datas += mo_files


a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=(
        [(str(GETTEXTPO), "."), (str(ENCHANT_HUNSPELL), "enchant/lib/enchant-2")]
        + [(str(path), IMMODULES_DEST) for path in IMMODULES]
    ),
    datas=datas,
    hiddenimports=common.hiddenimports(),
    # Adwaita is bundled above.
    hooksconfig=common.hooksconfig(LANGUAGES, {"GtkSpell": "3.0"}, icons=["hicolor"], themes=["Adwaita"]),
    hookspath=[str(ROOT / "devsupport" / "packaging" / "linux" / "pyinstaller-hooks")],
    runtime_hooks=[str(ROOT / "devsupport" / "packaging" / "linux" / "pyi_rth_appimage.py")],
    excludes=common.EXCLUDES,
    noarchive=False,
)
a.datas = common.trim(a.datas, ROOT)
# The host's: they read the host's own font configuration, which can be
# newer than this build's (AppImage's own exclude list leaves them out too).
HOST_LIBRARIES = ("libfontconfig.so.1", "libfreetype.so.6")
a.binaries = [entry for entry in a.binaries if os.path.basename(entry[0]) not in HOST_LIBRARIES]

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

common.check_catalogs(a.datas, mo_files, LANGUAGES)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

# Not "virtaal": in the flat layout, an executable of that name next to
# the bundled modules stops "import virtaal.cli" finding the package.
EXE_OPTIONS = {**common.EXE_OPTIONS, "name": "Virtaal", "console": True}

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    **EXE_OPTIONS,
    # The flat layout: translate-toolkit's frozen data lookup expects
    # share/ next to the executable (see the Windows spec).
    contents_directory=".",
)

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, **common.COLLECT_OPTIONS)  # noqa: F821
