#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.widgets.welcomescreen import WelcomeScreen

BUTTON_NAMES = (
    'open', 'recent1', 'recent2', 'recent3', 'recent4', 'recent5',
    'tutorial', 'cheatsheet', 'features_more', 'manual', 'locguide',
    'feedback', 'report_bug',
)


def _real_builder():
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    return builder


def test_construction_wires_up_every_button():
    screen = WelcomeScreen(_real_builder())

    assert set(screen.widgets['buttons']) == set(BUTTON_NAMES)


def test_button_click_emits_button_clicked_with_its_name():
    screen = WelcomeScreen(_real_builder())
    emitted = []
    screen.connect('button-clicked', lambda _widget, name: emitted.append(name))

    screen.widgets['buttons']['tutorial'].clicked()

    assert emitted == ['tutorial']


def test_set_banner_image_loads_the_given_file(monkeypatch):
    screen = WelcomeScreen(_real_builder())
    calls = []
    monkeypatch.setattr(screen.widgets['img_banner'], 'set_from_file', calls.append)

    screen.set_banner_image('/path/to/banner.png')

    assert calls == ['/path/to/banner.png']


def test_raises_when_the_builder_has_no_welcome_screen_object():
    empty_builder = Gtk.Builder()

    with pytest.raises(ValueError):
        WelcomeScreen(empty_builder)
