#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Generates Contents/Info.plist for the macOS .app bundle (see
devsupport/packaging/macos/build.sh). Run with the same Python environment
`bin/virtaal` runs with - CFBundleDocumentTypes is derived from
translate-toolkit's factory.supported_files(), the same source the old
(dead, py2app-based) devsupport/mac-bundle/Info.plist got its document
types from, just generated fresh instead of hand-maintained.

Usage: generate_info_plist.py OUTPUT_PATH
"""

import plistlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from translate.storage import factory

from virtaal.__version__ import ver as virtaal_version
from virtaal.support.libi18n.lite import read_linguas

ROOT = Path(__file__).resolve().parents[3]

# LINGUAS codes whose plain "_" -> "-" form AppKit doesn't match to the
# user's language setting.
APPLE_LOCALIZATIONS = {"ca@valencia": "ca-ES-valencia"}


def document_types():
    types = []
    for description, extensions, mimetypes in factory.supported_files():
        if not extensions:
            continue
        types.append({
            "CFBundleTypeExtensions": [ext.lstrip("*.") for ext in extensions],
            "CFBundleTypeIconFile": "VirtaalDocument.icns",
            "CFBundleTypeMIMETypes": list(mimetypes) if mimetypes else [],
            "CFBundleTypeName": description,
            "CFBundleTypeRole": "Editor",
        })
    return types


def bundle_localizations(languages):
    """CFBundleLocalizations: without it AppKit runs the app in English
    whatever the user's language, so its own menu items, and the Help
    menu's search field, never localize."""
    return ["en"] + sorted(
        {APPLE_LOCALIZATIONS.get(lang, lang.replace("_", "-")) for lang in languages} - {"en"})


_VERSION_RE = re.compile(
    r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-.]?(a|alpha|b|beta|rc|dev)(\d*))?(?:\+.*)?$")
# Third-number offset per stage: a release sorts above its pre-releases.
_STAGES = {"dev": 0, "a": 0, "alpha": 0, "b": 30, "beta": 30, "rc": 60}
_FINAL = 99


def bundle_version(ver):
    """CFBundleVersion: up to three integers that macOS compares, and that
    must grow with every release (Launch Services opens documents with the
    copy that has the highest). X.Y.Z-stageN becomes X.Y.(Z*100 + stage):
    aN = N, bN = 30+N, rcN = 60+N, dev = 0, the release itself = 99, so
    1.0.0-rc3 is 1.0.63 and 1.0.0 is 1.0.99."""
    m = _VERSION_RE.match(ver)
    if not m:
        raise ValueError("Can't make a CFBundleVersion from %r" % ver)
    major, minor, patch, stage, number = m.groups()
    if stage is None:
        offset = _FINAL
    elif stage == "dev":
        # One slot only: devN builds can't be told apart.
        if int(number or 0):
            raise ValueError("Only an unnumbered dev version fits a CFBundleVersion, not %r" % ver)
        offset = _STAGES["dev"]
    else:
        n = int(number or 0)
        if not 1 <= n <= 29:
            raise ValueError("Pre-release number in %r must be 1 to 29 for CFBundleVersion" % ver)
        offset = _STAGES[stage] + n
    return "%d.%d.%d" % (int(major), int(minor), int(patch or 0) * 100 + offset)


def build_plist():
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "Virtaal",
        "CFBundleExecutable": "Virtaal",
        "CFBundleIconFile": "virtaal.icns",
        "CFBundleIdentifier": "org.translatehouse.virtaal",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Virtaal",
        "CFBundlePackageType": "APPL",
        # User-visible, so it keeps the pre-release label (as Firefox does);
        # CFBundleVersion is the machine-comparable one.
        "CFBundleShortVersionString": virtaal_version,
        "CFBundleVersion": bundle_version(virtaal_version),
        "NSHumanReadableCopyright": "Copyright 2007-2026 Translate. GNU General Public License.",
        # A guess, not rigorously tested against a matrix of older macOS
        # versions - matches roughly what current Homebrew itself expects.
        # Adjust if a real compatibility problem turns up.
        "LSMinimumSystemVersion": "10.15",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": document_types(),
        "CFBundleLocalizations": bundle_localizations(read_linguas(ROOT / "po" / "LINGUAS")),
    }


def main():
    if len(sys.argv) != 2:
        print("usage: generate_info_plist.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "wb") as f:
        plistlib.dump(build_plist(), f)


if __name__ == "__main__":
    main()
