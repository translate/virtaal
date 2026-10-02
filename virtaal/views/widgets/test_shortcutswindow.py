#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib

import pytest
from gi.repository import Gtk

from virtaal.common.platform import platform
from virtaal.views.widgets import shortcutswindow
from virtaal.views.widgets.shortcutswindow import SHORTCUT_GROUPS, ShortcutsWindow


def test_every_group_has_a_title_and_at_least_one_shortcut():
    for title, shortcuts in SHORTCUT_GROUPS:
        assert title
        assert len(shortcuts) > 0
        for accelerator, description in shortcuts:
            assert accelerator
            assert description


def test_construction_builds_a_window_from_every_group():
    parent = Gtk.Window()

    window = ShortcutsWindow(parent)

    assert window.get_transient_for() is parent
    window.destroy()
    parent.destroy()


@pytest.fixture
def _restore_shortcuts_module(monkeypatch):
    yield
    monkeypatch.undo()
    importlib.reload(shortcutswindow)


@pytest.mark.parametrize('is_mac, accelerator', [(True, '<Primary>i'), (False, '<Alt>Return')])
def test_properties_shortcut_matches_the_platform(monkeypatch, _restore_shortcuts_module, is_mac, accelerator):
    # Cmd+I is the macOS convention for an item's info (Finder's Get Info).
    monkeypatch.setattr(platform, 'is_mac', is_mac)
    module = importlib.reload(shortcutswindow)

    shortcuts = dict((description, accel) for _title, group in module.SHORTCUT_GROUPS for accel, description in group)

    assert shortcuts['Show file properties and statistics'] == accelerator


def test_save_as_is_listed():
    shortcuts = dict((description, accel) for _title, group in SHORTCUT_GROUPS for accel, description in group)

    assert shortcuts['Save the current file under a new name'] == '<Primary><Shift>s'


@pytest.mark.parametrize('is_mac, accelerator', [(True, '<Primary>slash'), (False, '<Primary>question')])
def test_keyboard_shortcuts_shortcut_matches_the_platform(monkeypatch, _restore_shortcuts_module, is_mac, accelerator):
    # macOS reserves Cmd+? for opening the Help menu.
    monkeypatch.setattr(platform, 'is_mac', is_mac)
    module = importlib.reload(shortcutswindow)

    shortcuts = dict((description, accel) for _title, group in module.SHORTCUT_GROUPS for accel, description in group)

    assert shortcuts['Show this Keyboard Shortcuts window'] == accelerator
