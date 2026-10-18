#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The oldest macOS a bundle runs on: the highest minimum among its Mach-O
files (LC_BUILD_VERSION minos, or LC_VERSION_MIN_MACOSX).

    minimum_macos.py --check Virtaal.app

fails when the app's LSMinimumSystemVersion is lower than that, as it would
then start on a macOS its libraries can't load on (#4369).
"""

import plistlib
import re
import subprocess
import sys
from pathlib import Path

MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
}


def is_macho(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) in MACHO_MAGIC
    except OSError:
        return False


def _version_key(version):
    return tuple(int(part) for part in version.split("."))


def minimum_from_load_commands(text):
    """The minimum macOS in otool -l output, or None."""
    found = re.findall(r"cmd LC_BUILD_VERSION\b.*?\bminos (\S+)", text, re.S)
    found += re.findall(r"cmd LC_VERSION_MIN_MACOSX\b.*?\bversion (\S+)", text, re.S)
    return max(found, key=_version_key) if found else None


def binary_minimum(path):
    out = subprocess.run(["otool", "-l", str(path)], capture_output=True, text=True).stdout
    return minimum_from_load_commands(out)


def minimum_macos(paths):
    """The highest minimum macOS among the Mach-O files in paths."""
    found = [v for v in (binary_minimum(p) for p in paths if is_macho(p)) if v]
    if not found:
        raise ValueError("no Mach-O file with a minimum macOS version")
    return max(found, key=_version_key)


def check(app):
    app = Path(app)
    with open(app / "Contents" / "Info.plist", "rb") as f:
        declared = plistlib.load(f).get("LSMinimumSystemVersion", "0")
    needed = minimum_macos(p for p in (app / "Contents").rglob("*") if p.is_file() and not p.is_symlink())
    if _version_key(declared) < _version_key(needed):
        print("%s declares LSMinimumSystemVersion %s, but its binaries need macOS %s"
              % (app.name, declared, needed), file=sys.stderr)
        return 1
    print("%s: LSMinimumSystemVersion %s, binaries need macOS %s" % (app.name, declared, needed))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--check":
        sys.exit("usage: minimum_macos.py --check APP")
    sys.exit(check(sys.argv[2]))
