# Run PyInstaller with this spec from the repo root:
#   pyinstaller -y devsupport/packaging/macos/virtaal.spec
# (or via devsupport/packaging/macos/build_standalone.sh, which also
# handles the mo-compile prerequisite - see that script's header for why
# this exists alongside build.sh rather than replacing it.)
#
# The parts shared with the Windows spec are in
# devsupport/packaging/pyinstaller_common.py.
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.getcwd())
PACKAGING = ROOT / "devsupport" / "packaging" / "macos"

sys.path.insert(0, str(ROOT))
from virtaal.__version__ import ver as virtaal_version  # noqa: E402
from virtaal.support.libi18n.lite import bundle_languages  # noqa: E402

sys.path.insert(0, str(PACKAGING))
from generate_info_plist import bundle_localizations, document_types  # noqa: E402
from minimum_macos import minimum_macos  # noqa: E402

sys.path.insert(0, str(ROOT / "devsupport" / "packaging"))
import pyinstaller_common as common  # noqa: E402

LANGUAGES = common.languages(ROOT)
mo_files = common.mo_files(ROOT)


def _brew_prefix(formula):
    try:
        return Path(subprocess.run(
            ["brew", "--prefix", formula], capture_output=True, text=True, check=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path("/nonexistent")


# gtkosx_application_init() (gtk-mac-integration's own C code) rebinds
# its gettext domain to <bundle>/Contents/Resources/share/locale
# whenever it detects real bundle identity - true for every frozen
# build - so without its own locale files landing there too, the
# "Hide"/"Quit"/"Services"/"Show All"/"About %s" strings it builds
# itself always fall back to English, regardless of UI language.
_gtkmac_locale_dir = _brew_prefix("gtk-mac-integration") / "share" / "locale"
# libgettextpo, for the msgfmt check (virtaal/support/gettextpo.py). Loaded
# with ctypes, so nothing else pulls it in.
GETTEXTPO = _brew_prefix("gettext") / "lib" / "libgettextpo.0.dylib"
if not GETTEXTPO.is_file():
    raise SystemExit("libgettextpo not found: %s" % GETTEXTPO)
# And the Homebrew libraries it links, which it looks for at the top of
# Frameworks/. On Intel nothing else puts these there: pycurl's own
# libunistring goes in its .dylibs/, and the libintl there is an older one
# (without gl_get_setlocale_null_lock) unless it's this one.
GETTEXTPO_DEPS = [Path(line.split()[0]) for line in subprocess.run(
    ["otool", "-L", str(GETTEXTPO)], capture_output=True, text=True, check=True,
).stdout.splitlines()[2:] if line.split()[0].startswith(("/opt/homebrew/", "/usr/local/"))]

# Adwaita, as a run from source has (not its cursors: GTK uses macOS's).
# Its icons are SVG, so they need librsvg's GdkPixbuf loader too.
ADWAITA = _brew_prefix("adwaita-icon-theme") / "share" / "icons" / "Adwaita"
ADWAITA_PARTS = ["index.theme", "symbolic", "scalable", "16x16"]
SVG_LOADER = (_brew_prefix("librsvg") / "lib" / "gdk-pixbuf-2.0" / "2.10.0"
              / "loaders" / "libpixbufloader_svg.so")
for _required in [ADWAITA / part for part in ADWAITA_PARTS] + [SVG_LOADER]:
    if not _required.exists():
        raise SystemExit("Not found (brew install adwaita-icon-theme librsvg): %s" % _required)

gtkmac_mo_files = [
    (str(p), str(Path("share", "locale") / p.relative_to(_gtkmac_locale_dir).parent))
    for p in (_gtkmac_locale_dir.rglob("*.mo") if _gtkmac_locale_dir.is_dir() else [])
    if p.relative_to(_gtkmac_locale_dir).parts[0] in bundle_languages(LANGUAGES)
]

# build_standalone.sh stages this (Intel builds only) from an old,
# self-contained pyenchant wheel - see that script's own comment.
# pan_app.py points PYENCHANT_LIBRARY_PATH at it, frozen+Intel only;
# absent here just means an arm64 build, same as today.
ENCHANT_INTEL_DIR = ROOT / "build" / "enchant_intel" / "enchant"
_bundle_enchant = ENCHANT_INTEL_DIR.is_dir()

datas = common.datas(ROOT) + [
    # CFBundleTypeIconFile below (via document_types()) names this
    # file directly, but PyInstaller's BUNDLE step only auto-copies
    # the icon passed to EXE/BUNDLE's own icon= argument - anything
    # referenced solely from info_plist needs its own datas entry to
    # actually land in Contents/Resources.
    (str(ROOT / "devsupport" / "mac-bundle" / "VirtaalDocument.icns"), "."),
]
datas += [
    (str(ADWAITA / part), "share/icons/Adwaita" if part == "index.theme" else "share/icons/Adwaita/" + part)
    for part in ADWAITA_PARTS
]
datas += mo_files + gtkmac_mo_files
if _bundle_enchant:
    datas.append((str(ENCHANT_INTEL_DIR), "share/enchant_intel"))

a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=(
        [(str(GETTEXTPO), ".")] + [(str(dep), ".") for dep in GETTEXTPO_DEPS]
        + [(str(SVG_LOADER), "lib/gdk-pixbuf/loaders")]
    ),
    datas=datas,
    hiddenimports=common.hiddenimports(enchant=_bundle_enchant),
    hooksconfig=common.hooksconfig(
        LANGUAGES,
        # Optional native macOS menu-bar integration (mainview.py's
        # try/except-gated GtkosxApplication block) - statically imported,
        # so the gi hook would bundle it regardless; declared to match the
        # gi.require_version() call rather than whatever the hook guesses.
        module_versions={"GtkosxApplication": "1.0"},
        # Not every theme in Homebrew's share/icons: Adwaita is
        # bundled above, without its cursors.
        icons=["hicolor"],
    ),
    excludes=(
        common.EXCLUDES
        # No bundled dylib for this build (arm64, or staging failed) -
        # exclude enchant rather than let it fall through to Homebrew's
        # own copy (this CI job installs it) and crash: two separate
        # glib/gobject stacks in one process split the ObjC runtime's
        # class registry.
        + ([] if _bundle_enchant else ["enchant"])
    ),
    noarchive=False,
)
a.datas = common.trim(a.datas, ROOT)

# The GdkPixbuf hook's loader cache lists gdk-pixbuf's own loaders only;
# add the SVG one, at the path the hook uses for the rest.
_LOADER_CACHE = next(src for dest, src, _kind in a.datas if dest == "lib/gdk-pixbuf/loaders.cache")
_svg_entry = subprocess.run(
    ["gdk-pixbuf-query-loaders", str(SVG_LOADER)], capture_output=True, text=True, check=True,
).stdout.replace('"' + str(SVG_LOADER.parent.parent), '"@executable_path/lib/gdk-pixbuf')
with open(_LOADER_CACHE, "a", encoding="utf-8") as _cache:
    _cache.write("\n" + "\n".join(line for line in _svg_entry.splitlines() if not line.startswith("#")) + "\n")

# The Toolkit's spelling check imports enchant.checker.
if _bundle_enchant and "enchant.checker" not in {entry[0] for entry in a.pure}:
    raise SystemExit("enchant.checker isn't bundled")

# gtkmac_mo_files are among the copies Virtaal's own catalogs must beat.
common.check_catalogs(a.datas, mo_files, LANGUAGES)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    icon=str(ROOT / "devsupport" / "virtaal.icns"),
    **common.EXE_OPTIONS,
)

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, **common.COLLECT_OPTIONS)  # noqa: F821

app = BUNDLE(  # noqa: F821
    coll,
    name="Virtaal.app",
    icon=str(ROOT / "devsupport" / "virtaal.icns"),
    bundle_identifier="org.translatehouse.virtaal",
    version=virtaal_version,
    info_plist={
        "CFBundleDisplayName": "Virtaal",
        "CFBundleName": "Virtaal",
        "CFBundleShortVersionString": virtaal_version,
        "CFBundleVersion": virtaal_version,
        "NSHumanReadableCopyright": common.COPYRIGHT,
        # Homebrew's bottles target the build machine's macOS (#4369).
        "LSMinimumSystemVersion": minimum_macos(src for _dest, src, _kind in a.binaries),
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "CFBundleDocumentTypes": document_types(),
        "CFBundleLocalizations": bundle_localizations(LANGUAGES),
    },
)
