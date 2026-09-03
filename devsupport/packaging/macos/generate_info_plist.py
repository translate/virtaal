#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Generates Contents/Info.plist for the macOS .app bundle (see
devsupport/packaging/macos/build.sh). Run with the same Python environment
`bin/virtaal` runs with - CFBundleDocumentTypes is derived from
translate-toolkit's factory.supported_files(), the same source the old
(dead, py2app-based) devsupport/mac-bundle/Info.plist got its document
types from, just generated fresh instead of hand-maintained.

Usage: generate_info_plist.py OUTPUT_PATH
"""

import plistlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from translate.storage import factory

from virtaal.__version__ import ver as virtaal_version


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


def build_plist():
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "Virtaal",
        "CFBundleExecutable": "Virtaal",
        "CFBundleIconFile": "virtaal.icns",
        "CFBundleIdentifier": "za.org.translate.virtaal",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Virtaal",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": virtaal_version,
        "CFBundleVersion": virtaal_version,
        "NSHumanReadableCopyright": "Copyright 2007-2026 Translate. GNU General Public License.",
        # A guess, not rigorously tested against a matrix of older macOS
        # versions - matches roughly what current Homebrew itself expects.
        # Adjust if a real compatibility problem turns up.
        "LSMinimumSystemVersion": "10.15",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": document_types(),
    }


def main():
    if len(sys.argv) != 2:
        print("usage: generate_info_plist.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "wb") as f:
        plistlib.dump(build_plist(), f)


if __name__ == "__main__":
    main()
