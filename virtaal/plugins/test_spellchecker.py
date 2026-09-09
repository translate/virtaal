#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for the spellchecker plugin.

These mostly avoid instantiating virtaal.plugins.spellchecker.Plugin
itself, since __init__ needs a full MainController/GTK unit view - out of
reach for a plain unit test. What's covered instead: the plugin's
dependency-free helper logic, and a regression check for the fix landed in
commit 7663e3e9 (the plugin silently failing to load because pyenchant was
never installed, not because of any GTK2/GTK3 incompatibility). The one
exception is the frozen-build check below, which is guaranteed to raise
before __init__ ever touches main_controller.
"""

import pytest

from virtaal.common.platform import platform
from virtaal.controllers.baseplugin import PluginUnsupported
from virtaal.plugins.spellchecker import Plugin, _dict_add_re


class _FakeEnchant:
    """Records what language code it was actually asked about, without
    needing real enchant/dictionaries installed."""

    def __init__(self, known_dicts):
        self.known_dicts = known_dicts
        self.checked = []

    def dict_exists(self, language):
        self.checked.append(language)
        return language in self.known_dicts


def test_dict_add_re_matches_gtkspell_suggestion():
    """_dict_add_re extracts the word from GtkSpell's context-menu label
    ('Add "x" to Dictionary'), which _fix_menu() then re-translates."""
    m = _dict_add_re.match('Add "virtaal" to Dictionary')
    assert m is not None
    assert m.group(1) == "virtaal"


def test_dict_add_re_no_match_on_unrelated_label():
    assert _dict_add_re.match("Ignore All") is None


@pytest.mark.parametrize("language,expected", [("pt", "pt_PT"), ("de", "de_DE")])
def test_on_unit_lang_changed_maps_to_country_variant(language, expected):
    """Regression: a `==` vs `=` typo made these branches no-ops, so 'pt'
    and 'de' were probed against enchant as themselves instead of the
    country variant, the same treatment 'en' already got correctly."""
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts={expected})
    plugin._seen_languages = {}
    plugin._enchant_languages = []

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=None, language=language)

    assert plugin.enchant.checked == [expected]


def test_unsupported_in_any_frozen_build(monkeypatch):
    """A frozen build never bundles a version-matched gtkspell3 - a
    system-found one can mismatch the frozen app's own bundled GTK3
    and crash outright."""
    monkeypatch.setattr(platform, 'is_frozen', True)
    with pytest.raises(PluginUnsupported):
        Plugin('spellchecker', None)


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
