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


@pytest.mark.parametrize('description, accelerator', [
    ('Next Unit and Advance State', '<Control>Return'),
    ('Next Unit and Reverse State', '<Control><Shift>Return'),
    ('Jump to the language-pair selector', '<Control>Tab'),
    ('Jump to the "Navigation:" mode selector', '<Control><Shift>Tab'),
])
def test_textbox_shortcuts_use_control_on_every_platform(description, accelerator):
    # Handled by the target textbox as literal Ctrl, never Cmd on macOS.
    shortcuts = dict((desc, accel) for _title, group in SHORTCUT_GROUPS for accel, desc in group)

    assert shortcuts[description] == accelerator


ARABIC_INDIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'


def _with_digits(monkeypatch, digits):
    import builtins
    real = builtins._
    monkeypatch.setattr(builtins, '_', lambda s: digits if s == '0123456789' else real(s))
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'en')


@pytest.mark.parametrize('digits, expected', [
    ('0123456789', '_2'),
    (ARABIC_INDIC_DIGITS, '_٢'),
])
def test_page_numbers_use_the_ui_languages_digits(monkeypatch, digits, expected):
    # GTK titles the pages of a long section itself, as it adds them.
    _with_digits(monkeypatch, digits)
    window = ShortcutsWindow.__new__(ShortcutsWindow)
    stack = Gtk.Stack()
    stack.connect('add', window._on_page_added)
    page = Gtk.Box()

    stack.add_titled(page, 'page2', '_2')

    assert stack.child_get_property(page, 'title') == expected


@pytest.mark.parametrize('accelerator, expected', [
    ('<Meta>o', [['⌘', 'O']]),
    ('<Meta><Shift>s', [['⇧', '⌘', 'S']]),
    ('<Control><Shift>Return', [['⌃', '⇧', '↩']]),
    ('<Alt>Left', [['⌥', '←']]),
    ('<Shift>Tab', [['⇧', '⇥']]),
    ('Escape', [['⎋']]),
    ('<Meta>f F3', [['⌘', 'F'], ['F3']]),
])
def test_mac_keycaps_use_apple_symbols_and_order(accelerator, expected):
    assert shortcutswindow.mac_keycaps(accelerator) == expected


def test_mac_keycaps_reject_an_unparseable_accelerator():
    assert shortcutswindow.mac_keycaps('<Meta>o <Bogus>') is None


def _keycap_texts(window):
    rows = []
    for label in shortcutswindow._shortcut_labels(window):
        rows.append([child.get_text() for child in label.get_children()])
    return rows


def test_mac_window_relabels_every_row_including_search_copies(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)
    parent = Gtk.Window()

    window = ShortcutsWindow(parent)
    rows = _keycap_texts(window)

    n_shortcuts = sum(len(group) for _title, group in SHORTCUT_GROUPS)
    assert len(rows) == 2 * n_shortcuts
    assert ['⇥'] in rows
    assert not any('+' in row or 'Shift' in row for row in rows)
    window.destroy()
    parent.destroy()


def test_other_platforms_keep_gtks_own_labels(monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    parent = Gtk.Window()

    window = ShortcutsWindow(parent)

    assert ['Shift', '+', 'Tab'] in _keycap_texts(window)
    window.destroy()
    parent.destroy()
