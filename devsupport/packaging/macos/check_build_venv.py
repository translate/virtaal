#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fail if the build venv can see a package virtaal doesn't depend on.

PyInstaller bundles whatever an import trace reaches, including guarded
optional imports, so a stray package can vendor a native library that
shadows GTK's (#3871).
Set VIRTAAL_ALLOW_EXTRA_PACKAGES=1 to only warn.
"""

import importlib.metadata
import os
import re
import sys

from packaging.requirements import Requirement

# GTK bindings are system prerequisites, not declared dependencies.
ROOTS = [
    "virtaal[spellcheck]",
    "PyGObject",
    "pycairo",
    "pyinstaller",
    "pip",
    "setuptools",
    "wheel",
]


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def closure(roots):
    seen = set()
    pending = [Requirement(r) for r in roots]
    while pending:
        req = pending.pop()
        name = normalize(req.name)
        try:
            dist = importlib.metadata.distribution(req.name)
        except importlib.metadata.PackageNotFoundError:
            continue
        seen.add(name)
        for spec in dist.requires or []:
            dep = Requirement(spec)
            if dep.marker and not any(
                dep.marker.evaluate({"extra": extra}) for extra in req.extras | {""}
            ):
                continue
            if normalize(dep.name) not in seen:
                pending.append(dep)
    return seen


def main():
    installed = {
        normalize(d.metadata["Name"]): "%s (%s)" % (d.metadata["Name"], d.locate_file(""))
        for d in importlib.metadata.distributions()
    }
    extra = sorted(installed[n] for n in installed.keys() - closure(ROOTS))
    if not extra:
        return 0
    print(
        "Build venv can see packages virtaal doesn't depend on - PyInstaller\n"
        "may bundle them and shadow GTK's native libraries (see #3871):\n  "
        + "\n  ".join(extra)
        + "\nUninstall them, or set VIRTAAL_ALLOW_EXTRA_PACKAGES=1.",
        file=sys.stderr,
    )
    return 0 if os.environ.get("VIRTAAL_ALLOW_EXTRA_PACKAGES") == "1" else 1


if __name__ == "__main__":
    sys.exit(main())
