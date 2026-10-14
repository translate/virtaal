#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.widgets import welcomescreen
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


def test_set_banner_image_loads_the_file_and_scrolls_over_all_of_it():
    screen = WelcomeScreen(_real_builder())
    banner = screen.widgets['img_banner']

    screen.set_banner_image('share/virtaal/welcome_screen_banner.png')

    assert banner.get_pixbuf().get_width() == 2000
    assert banner.get_parent().get_size()[0] == 2000


@pytest.mark.parametrize('direction', [Gtk.TextDirection.LTR, Gtk.TextDirection.RTL])
def test_the_banner_shows_the_end_its_logo_is_at(direction):
    # The banners are 2000px wide; the right-to-left ones have the logo
    # at the right end.
    screen = WelcomeScreen(_real_builder())
    screen.set_banner_image('share/virtaal/welcome_screen_banner_rtl.png')
    window = Gtk.OffscreenWindow()
    window.set_direction(direction)
    screen.set_direction(direction)
    banner = screen.widgets['img_banner']
    banner.get_parent().set_direction(direction)
    window.add(screen)
    window.set_size_request(400, 300)
    window.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    layout = banner.get_parent()
    width = layout.get_allocation().width
    scrolled_to = 0 if direction == Gtk.TextDirection.LTR else 2000 - width
    assert 0 < width < 2000
    assert layout.props.hadjustment.get_value() == scrolled_to
    window.destroy()


def test_raises_when_the_builder_has_no_welcome_screen_object():
    empty_builder = Gtk.Builder()

    with pytest.raises(ValueError):
        WelcomeScreen(empty_builder)


# feature list / exp_features expander - #3779 #

def test_txt_features_is_not_keyboard_navigable():
    screen = WelcomeScreen(_real_builder())

    assert screen.widgets['txt_features'].get_can_focus() is False


def test_feature_view_background_is_transparent(monkeypatch):
    bg_calls = []
    monkeypatch.setattr(welcomescreen, 'set_widget_bg_color', lambda widget, color: bg_calls.append((widget, color)))
    idle_calls = []
    monkeypatch.setattr(welcomescreen.GLib, 'idle_add', lambda func, *a, **k: idle_calls.append((func, a)))

    screen = WelcomeScreen(_real_builder())
    func, args = idle_calls[0]
    func(*args)

    assert bg_calls == [(screen.widgets['txt_features'], 'transparent')]


def test_features_more_starts_unfocusable_while_collapsed():
    screen = WelcomeScreen(_real_builder())

    assert screen.widgets['exp_features'].get_expanded() is False
    assert screen.widgets['buttons']['features_more'].get_can_focus() is False


def test_features_more_becomes_focusable_once_expanded():
    screen = WelcomeScreen(_real_builder())

    screen.widgets['exp_features'].set_expanded(True)

    assert screen.widgets['buttons']['features_more'].get_can_focus() is True


def test_features_more_becomes_unfocusable_again_once_collapsed():
    screen = WelcomeScreen(_real_builder())
    screen.widgets['exp_features'].set_expanded(True)

    screen.widgets['exp_features'].set_expanded(False)

    assert screen.widgets['buttons']['features_more'].get_can_focus() is False
