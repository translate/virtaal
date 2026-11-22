#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import re

ISS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "devsupport", "packaging", "windows", "virtaal.iss",
)


def _install_delete_names():
    with open(ISS, encoding="utf-8-sig") as f:
        text = f.read()
    section = re.search(r"^\[InstallDelete\]\n(.*?)(?=^\[)", text, re.M | re.S).group(1)
    return re.findall(r'^Type: \w+; Name: "([^"]+)"', section, re.M)


def test_an_upgrade_removes_the_previous_builds_translations():
    # A language dropped from po/LINGUAS would otherwise still be offered.
    assert "{app}\\share\\locale" in _install_delete_names()


def test_an_upgrade_removes_the_previous_builds_gio_modules():
    assert "{app}\\lib\\gio\\modules" in _install_delete_names()


def test_an_upgrade_only_deletes_inside_the_install_directory():
    for name in _install_delete_names():
        assert name.startswith("{app}\\") and name != "{app}\\"
