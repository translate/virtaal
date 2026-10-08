#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gtk
from translate.storage.workflow import StateEnum

from virtaal.views import theme
from virtaal.views.theme import set_widget_bg_color, set_widget_fg_color


def test_set_widget_fg_color_accepts_a_hex_colour():
    # A malformed generated CSS string raises Gtk.CssProvider's own
    # GLib.GError - this is really a check that the string built here
    # is valid CSS, not just that the call completes.
    label = Gtk.Label()
    set_widget_fg_color(label, '#666')


def test_set_widget_fg_color_accepts_a_named_colour():
    label = Gtk.Label()
    set_widget_fg_color(label, 'grey')


def test_set_widget_bg_color_accepts_a_hex_colour():
    label = Gtk.Label()
    set_widget_bg_color(label, '#666')


def test_set_widget_bg_color_accepts_a_named_colour():
    label = Gtk.Label()
    set_widget_bg_color(label, 'grey')


def test_has_good_contrast_black_on_white():
    assert theme.has_good_contrast('#000', '#fff') is True


def test_has_good_contrast_false_for_close_greys():
    # reasonably distinguishable, but not good enough for text:
    assert theme.has_reasonable_contrast('#777', '#888') is True
    assert theme.has_good_contrast('#777', '#888') is False


def test_has_reasonable_contrast_false_for_identical_colours():
    assert theme.has_reasonable_contrast('#fff', '#fff') is False


def test_distinguishable_from_keeps_colour_with_good_contrast():
    assert theme._distinguishable_from('#fff', '#000', '#000') == '#000'


def test_distinguishable_from_falls_back_when_indistinguishable():
    theme.INVERSE = False
    try:
        # '#eee' on '#eee' would vanish into the page background entirely
        assert theme._distinguishable_from('#eee', '#000', '#eee') == '#fff'
    finally:
        theme.INVERSE = False


def test_distinguishable_from_falls_back_to_black_when_inverse():
    theme.INVERSE = True
    try:
        assert theme._distinguishable_from('#333', '#fff', '#333') == '#000'
    finally:
        theme.INVERSE = False


def test_distinguishable_from_keeps_a_highlight_the_fallback_would_hide():
    # #3968: yellow on a white page is below the contrast threshold, but the
    # '#fff' fallback is identical to the page and would hide it completely.
    theme.INVERSE = False
    try:
        assert theme._distinguishable_from('#ffffff', '#000000', '#ffff70') == '#ffff70'
    finally:
        theme.INVERSE = False


def test_distinguishable_from_keeps_original_when_fallback_also_unreadable():
    theme.INVERSE = False
    try:
        # the '#fff' fallback wouldn't be readable against this near-white fg,
        # so the original (still indistinguishable from bg) colour is kept
        assert theme._distinguishable_from('#ddd', '#eee', '#ddd') == '#ddd'
    finally:
        theme.INVERSE = False


def test_update_style_detects_a_light_theme():
    # get_background_color() always returns fully transparent in
    # current GTK3, regardless of the widget's real theme - is_inverse()
    # then always read that as "darker than the foreground", so every
    # theme-dependent colour app-wide was picked for the wrong theme
    # entirely (#3240), not just badly. gtk-application-prefer-dark-theme
    # is a process-wide GtkSettings property another test may already
    # have flipped - pin and restore it so this test doesn't depend on
    # what ran before it.
    settings = Gtk.Settings.get_default()
    original = settings.get_property('gtk-application-prefer-dark-theme')
    settings.set_property('gtk-application-prefer-dark-theme', False)
    try:
        win = Gtk.Window()
        lbl = Gtk.Label()
        win.add(lbl)
        win.show_all()

        theme.update_style(lbl)

        assert theme.INVERSE is False
    finally:
        settings.set_property('gtk-application-prefer-dark-theme', original)


@pytest.mark.parametrize('state_n, styled', [
    (StateEnum.EMPTY, False),
    (StateEnum.NEEDS_WORK, True),
    (StateEnum.REJECTED, True),
    (StateEnum.NEEDS_REVIEW, True),
    (StateEnum.UNREVIEWED - 1, True),
    (StateEnum.UNREVIEWED, False),
    (StateEnum.FINAL, False),
])
def test_state_style_covers_the_states_needing_work(state_n, styled):
    expected = {'background': theme.current_theme['fuzzy_row_bg']} if styled else {}

    assert theme.state_style(state_n) == expected


def test_state_style_follows_the_current_theme(monkeypatch):
    monkeypatch.setitem(theme.current_theme, 'fuzzy_row_bg', '#123456')

    assert theme.state_style(StateEnum.NEEDS_WORK) == {'background': '#123456'}


def test_unit_style_uses_the_saved_state():
    from translate.storage import pypo
    unit = pypo.pofile().addsourceunit('Open')
    unit.target = 'Maak oop'
    unit.markfuzzy(True)

    assert theme.unit_style(unit) == theme.state_style(StateEnum.NEEDS_WORK)


@pytest.mark.parametrize('fuzzy, styled', [(True, True), (False, False)])
def test_unit_style_of_a_format_without_states_follows_fuzzy(fuzzy, styled):
    unit = SimpleNamespace(STATE={}, isfuzzy=lambda: fuzzy)

    assert bool(theme.unit_style(unit)) is styled
