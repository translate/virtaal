#!/usr/bin/env python
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

"""Tests for the spellchecker plugin.

These deliberately avoid instantiating virtaal.plugins.spellchecker.Plugin
itself, since __init__ needs a full MainController/GTK unit view - out of
reach for a plain unit test. What's covered instead: the plugin's
dependency-free helper logic, and a regression check for the fix landed in
commit 7663e3e9 (the plugin silently failing to load because pyenchant was
never installed, not because of any GTK2/GTK3 incompatibility).
"""

import pytest

from virtaal.plugins.spellchecker import _dict_add_re


def test_dict_add_re_matches_gtkspell_suggestion():
    """_dict_add_re extracts the word from GtkSpell's context-menu label
    ('Add "x" to Dictionary'), which _fix_menu() then re-translates."""
    m = _dict_add_re.match('Add "virtaal" to Dictionary')
    assert m is not None
    assert m.group(1) == "virtaal"


def test_dict_add_re_no_match_on_unrelated_label():
    assert _dict_add_re.match("Ignore All") is None


def test_spellchecker_dependencies_importable():
    """enchant and GtkSpell 3.0 must both be importable, and enchant must
    report at least one available dictionary/provider, for the
    spellchecker plugin to load at all.

    Skips (rather than fails) when these optional system dependencies
    aren't installed, since the plugin is designed to degrade gracefully
    without them - see .claude/skills/run-virtaal/SKILL.md. CI always
    installs them (.github/workflows/ci.yml), so this is a real, enforced
    check there rather than a permanent skip.
    """
    try:
        import enchant
    except ImportError:
        pytest.skip("pyenchant not installed - optional, see SKILL.md")

    try:
        import gi
        gi.require_version("GtkSpell", "3.0")
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        pytest.skip("GtkSpell 3.0 typelib not installed - optional, see SKILL.md")

    assert enchant.list_languages(), (
        "enchant imported but reports no available dictionaries/providers "
        "- check the enchant backend (hunspell/aspell) is installed"
    )
