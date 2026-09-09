#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for update_check's pure version-comparison logic - the one
part of the update check that's cheaply, deterministically testable
without a real network call."""

import pytest

from virtaal.support.update_check import is_newer


@pytest.mark.parametrize("remote,local,expected", [
    # Same core version, different beta numbers - the main case that
    # matters while every published release is still a prerelease.
    ("v1.0.0-beta2", "1.0.0-beta1", True),
    ("v1.0.0-beta1", "1.0.0-beta2", False),
    ("v1.0.0-beta1", "1.0.0-beta1", False),
    # A stable release outranks any prerelease of the same core version.
    ("v1.0.0", "1.0.0-beta5", True),
    ("v1.0.0-rc1", "1.0.0", False),
    # alpha < beta < rc for the same core version.
    ("v1.0.0-rc1", "1.0.0-beta9", True),
    ("v1.0.0-beta1", "1.0.0-alpha9", True),
    # Plain core-version ordering.
    ("v1.1.0", "1.0.0", True),
    ("v2.0.0", "1.9.9", True),
    ("v1.0.0", "1.0.1", False),
    # A leading "v" on either side shouldn't matter.
    ("1.0.1", "v1.0.0", True),
])
def test_is_newer(remote, local, expected):
    assert is_newer(remote, local) is expected


def test_is_newer_unparseable_fails_closed():
    """Malformed input never claims an update exists - fail closed,
        not guess."""
    assert is_newer("not-a-version", "1.0.0") is False
    assert is_newer("v1.0.0", "not-a-version") is False
    assert is_newer("", "1.0.0") is False
