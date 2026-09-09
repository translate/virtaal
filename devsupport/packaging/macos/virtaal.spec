# Run PyInstaller with this spec from the repo root:
#   pyinstaller -y devsupport/packaging/macos/virtaal.spec
# (or via devsupport/packaging/macos/build_standalone.sh, which also
# handles the mo-compile prerequisite - see that script's header for why
# this exists alongside build.sh rather than replacing it.)
#
# Adapted for this codebase's GTK3 (not GTK4) and its two dynamic-import
# points PyInstaller's static analysis can't see on its own: virtaal's own
# directory-scanning plugin loader (virtaal/controllers/plugincontroller.py
# __import__()s plugins by name at runtime, not via a static import
# anywhere), and virtaal/support/tmserver.py (only ever reached via bin/
# virtaal's own runpy-based "--run-module" dispatch, itself only reached at
# runtime from a subprocess argv check - see localtm.py). collect_submodules
# across the whole virtaal package (not just .plugins) is the simplest way
# to not have to enumerate either by hand, at negligible cost for a
# pure-Python package this size.
#
# Same reasoning covers translate.storage: factory.getobject() imports
# a format's backend module by a runtime-computed string, invisible to
# PyInstaller unless collected explicitly too.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(os.getcwd())
PACKAGING = ROOT / "devsupport" / "packaging" / "macos"

sys.path.insert(0, str(ROOT))
from virtaal.__version__ import ver as virtaal_version  # noqa: E402

sys.path.insert(0, str(PACKAGING))
from generate_info_plist import document_types  # noqa: E402

COPYRIGHT = "Copyright 2007-2026 Translate. GNU General Public License."

# translate-toolkit ships its own small data directory (translate/share/ -
# langmodels/, the ngram language-model files translate.lang.identify.
# LanguageIdentifier needs for auto-detection, plus stoplist-en) that
# translate.misc.file_discovery's frozen-mode lookup expects to find
# alongside virtaal's own share/virtaal and share/icons below - it's a
# third-party package's data, not virtaal's own, so it was never in this
# datas list at all. Without it, the language-pair selector (which
# triggers get_detected_langs(), langcontroller.py) crashes with
# ValueError: Could not find "langmodels". Lands under the same "share"
# destination as everything else below, so build_standalone.sh's existing
# Contents/MacOS/share -> ../Resources/share symlink already covers it,
# no extra workaround needed here. Located dynamically (not a hardcoded
# venv path) via the actually-imported translate module, same style as
# everything else in this file.
import translate  # noqa: E402
TRANSLATE_SHARE = Path(translate.__file__).parent / "share"

mo_files = [
    (str(p), str(Path("share", "locale") / p.relative_to(ROOT / "mo").parent / "LC_MESSAGES"))
    for p in (ROOT / "mo").rglob("*.mo")
]

# build_standalone.sh stages this (Intel builds only) from an old,
# self-contained pyenchant wheel - see that script's own comment.
# pan_app.py points PYENCHANT_LIBRARY_PATH at it, frozen+Intel only;
# absent here just means an arm64 build, same as today.
ENCHANT_INTEL_DIR = ROOT / "build" / "enchant_intel" / "enchant"
_bundle_enchant = ENCHANT_INTEL_DIR.is_dir()

datas = [
    (str(ROOT / "share" / "virtaal"), "share/virtaal"),
    (str(ROOT / "share" / "icons"), "share/icons"),
    (str(TRANSLATE_SHARE), "share"),
    # CFBundleTypeIconFile below (via document_types()) names this
    # file directly, but PyInstaller's BUNDLE step only auto-copies
    # the icon passed to EXE/BUNDLE's own icon= argument - anything
    # referenced solely from info_plist needs its own datas entry to
    # actually land in Contents/Resources.
    (str(ROOT / "devsupport" / "mac-bundle" / "VirtaalDocument.icns"), "."),
    # virtaal/support/authors.py reads this at the bundle root - it
    # stays a real top-level file (not under share/) so it's still
    # recognised by GitHub/the AUTHORS convention in a checkout too.
    (str(ROOT / "AUTHORS.md"), "."),
] + mo_files
if _bundle_enchant:
    datas.append((str(ENCHANT_INTEL_DIR), "share/enchant_intel"))

a = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "virtaal")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=(
        collect_submodules("virtaal")
        + collect_submodules("translate.storage")
        + (collect_submodules("enchant") if _bundle_enchant else [])
    ),
    hooksconfig={
        "gi": {
            "module-versions": {
                "Gtk": "3.0",
                # Optional native macOS menu-bar integration
                # (mainview.py's try/except-gated GtkosxApplication block) -
                # statically imported, so PyInstaller's gi hook would try
                # to bundle it regardless; declared explicitly to match the
                # actual gi.require_version() call rather than relying on
                # whatever the hook guesses.
                "GtkosxApplication": "1.0",
            },
        },
    },
    # devsupport isn't needed at runtime in a frozen build - its one
    # consumer (profiling support) is already `if not packaged:`-gated
    # off in bin/virtaal itself.
    excludes=(
        ["FixTk", "tcl", "tk", "_tkinter", "tkinter", "Tkinter", "devsupport"]
        # No bundled dylib for this build (arm64, or staging failed) -
        # exclude enchant rather than let it fall through to Homebrew's
        # own copy (this CI job installs it) and crash: two separate
        # glib/gobject stacks in one process split the ObjC runtime's
        # class registry.
        + ([] if _bundle_enchant else ["enchant"])
    ),
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
    icon=str(ROOT / "devsupport" / "virtaal.icns"),
    codesign_identity=os.getenv("CODESIGN_IDENTITY"),
)

coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="virtaal"
)

app = BUNDLE(  # noqa: F821
    coll,
    name="Virtaal.app",
    icon=str(ROOT / "devsupport" / "virtaal.icns"),
    bundle_identifier="za.org.translate.virtaal",
    version=virtaal_version,
    info_plist={
        "CFBundleDisplayName": "Virtaal",
        "CFBundleName": "Virtaal",
        "CFBundleShortVersionString": virtaal_version,
        "CFBundleVersion": virtaal_version,
        "NSHumanReadableCopyright": COPYRIGHT,
        # Same guess as generate_info_plist.py's dev-convenience bundle -
        # not rigorously tested against a matrix of older macOS versions.
        "LSMinimumSystemVersion": "10.15",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "CFBundleDocumentTypes": document_types(),
    },
)
