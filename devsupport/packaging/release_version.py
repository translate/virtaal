#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Numeric versions for the macOS and Windows bundles, which compare
versions as integers only and must see every release grow: a beta, an
rc and the release itself each get a higher number."""

import re

_VERSION_RE = re.compile(
    r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-.]?(a|alpha|b|beta|rc|dev)(\d*))?(?:\+.*)?$")
# Stage number per pre-release: a release sorts above its pre-releases.
_STAGES = {"dev": 0, "a": 0, "alpha": 0, "b": 30, "beta": 30, "rc": 60}
_FINAL = 99


def release_numbers(ver):
    """(major, minor, patch, stage) for X.Y.Z-stageN: stage is aN = N,
    bN = 30+N, rcN = 60+N, dev = 0 and the release itself 99, so
    1.0.0-rc3 is (1, 0, 0, 63) and 1.0.0 is (1, 0, 0, 99)."""
    m = _VERSION_RE.match(ver)
    if not m:
        raise ValueError("Can't make a numeric version from %r" % ver)
    major, minor, patch, stage, number = m.groups()
    if stage is None:
        offset = _FINAL
    elif stage == "dev":
        # One slot only: devN builds can't be told apart.
        if int(number or 0):
            raise ValueError("Only an unnumbered dev version fits a numeric version, not %r" % ver)
        offset = _STAGES["dev"]
    else:
        n = int(number or 0)
        if not 1 <= n <= 29:
            raise ValueError("Pre-release number in %r must be 1 to 29" % ver)
        offset = _STAGES[stage] + n
    return int(major), int(minor), int(patch or 0), offset


def file_version(ver):
    """Windows filevers/prodvers: four 16-bit numbers, the stage last."""
    numbers = release_numbers(ver)
    if max(numbers) > 0xFFFF:
        raise ValueError("%r doesn't fit a Windows file version" % ver)
    return numbers
