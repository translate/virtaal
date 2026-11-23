#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import gi
import pytest
from gi.repository import Gtk, Pango

from virtaal.common.platform import platform
from virtaal.views import rendering
from virtaal.views.rendering import set_widget_font


def test_set_widget_font_accepts_a_family_and_point_size():
    # font: <Pango description> is accepted by Gtk.CssProvider but
    # rejected as "not a number" for some descriptions (e.g. a family
    # followed by a bare size, "Monospace 10") - family/size as their
    # own CSS properties avoids relying on that shorthand at all.
    label = Gtk.Label()
    set_widget_font(label, Pango.FontDescription('Monospace 10'))


def test_set_widget_font_accepts_an_absolute_size():
    label = Gtk.Label()
    desc = Pango.FontDescription('Sans 12px')
    assert desc.get_size_is_absolute()
    set_widget_font(label, desc)


def test_set_widget_font_passes_every_family_to_pango():
    label = Gtk.Label()
    set_widget_font(label, Pango.FontDescription('Monospace,Ebrima 10'))

    assert label.get_pango_context().get_font_description().get_family() == 'Monospace,Ebrima'


def _css_font(label):
    return label.get_pango_context().get_font_description()


def test_set_widget_font_keeps_the_size_for_a_family_only_font():
    # #4863: "Sans" has no size; 0pt drew no text.
    size = _css_font(Gtk.Label()).get_size()
    label = Gtk.Label()

    set_widget_font(label, Pango.FontDescription('Ebrima'))

    assert _css_font(label).get_family() == 'Ebrima'
    assert _css_font(label).get_size() == size != 0


def test_set_widget_font_keeps_the_family_for_a_size_only_font():
    family = _css_font(Gtk.Label()).get_family()
    label = Gtk.Label()

    set_widget_font(label, Pango.FontDescription('17'))

    assert _css_font(label).get_family() == family
    assert _css_font(label).get_size() == 17 * Pango.SCALE


# Settings without a family or size (#4863) #

@pytest.mark.parametrize('setting, expected', [
    ('Serif', 'Serif 11'),
    ('17', 'Mono 17'),
    ('Bold 17', 'Mono Bold 17'),
    ('Serif Italic', 'Serif Italic 11'),
    ('', 'Mono 11'),
    (None, 'Mono 11'),
    ('Serif 13px', 'Serif 13px'),
])
def test_complete_font_name_fills_in_the_default_family_and_size(monkeypatch, setting, expected):
    monkeypatch.setattr(rendering.pan_app, 'defaultfont', 'Mono 11')

    assert rendering.complete_font_name(setting) == expected


def test_complete_font_name_takes_only_the_family_and_size_from_the_default(monkeypatch):
    monkeypatch.setattr(rendering.pan_app, 'defaultfont', 'Mono Bold Italic 11')

    assert rendering.complete_font_name('Serif') == 'Serif 11'
    assert rendering.complete_font_name('17') == 'Mono 17'


def test_complete_font_name_keeps_a_complete_font_as_written(monkeypatch):
    monkeypatch.setattr(rendering.pan_app, 'defaultfont', 'Mono 11')

    assert rendering.complete_font_name('DejaVu Sans,Ebrima  12') == 'DejaVu Sans,Ebrima  12'


@pytest.mark.parametrize('fallbacks', [(), ('Ebrima',)])
@pytest.mark.parametrize('setting, family, size', [
    ('Serif', 'Serif', 11),
    ('17', 'Mono', 17),
    ('Serif 13', 'Serif', 13),
])
def test_source_and_target_fonts_get_the_default_family_and_size(monkeypatch, fallbacks, setting, family, size):
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: fallbacks)
    monkeypatch.setattr(rendering, '_font_descriptions', {})
    monkeypatch.setattr(rendering.pan_app, 'defaultfont', 'Mono 11')
    monkeypatch.setitem(rendering.pan_app.settings.language, 'sourcefont', setting)
    monkeypatch.setitem(rendering.pan_app.settings.language, 'targetfont', setting)

    for desc in (rendering.get_source_font_description(), rendering.get_target_font_description()):
        assert desc.get_family().split(',') == [family, *fallbacks]
        assert desc.get_size() == size * Pango.SCALE


# Font fallbacks #

def test_font_fallbacks_keep_the_size_and_style(monkeypatch):
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: ('Ebrima',))

    assert rendering.with_font_fallbacks('Segoe UI Bold 13') == 'Segoe UI,Ebrima Bold 13'


def test_font_fallbacks_are_added_once(monkeypatch):
    # Each MainView adds them to GTK's process-wide UI font.
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: ('Ebrima', 'Nirmala UI'))

    once = rendering.with_font_fallbacks('Segoe UI 9')

    assert rendering.with_font_fallbacks(once) == once == 'Segoe UI,Ebrima,Nirmala UI 9'


@pytest.mark.parametrize('font', ['12', 'Bold 12', ''])
def test_font_fallbacks_leave_a_font_without_a_family_alone(monkeypatch, font):
    # A fallback would replace GTK's default family, not follow it.
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: ('Ebrima',))

    assert rendering.with_font_fallbacks(font) == font


def test_font_fallbacks_leave_the_font_alone_without_fallbacks(monkeypatch):
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: ())

    assert rendering.with_font_fallbacks('Sans 10') == 'Sans 10'


@pytest.mark.parametrize('is_mac, is_windows, first', [
    (True, False, 'Kohinoor Devanagari'),
    (False, True, 'Ebrima'),
    (False, False, None),
])
def test_font_fallbacks_per_platform(monkeypatch, is_mac, is_windows, first):
    monkeypatch.setattr(platform, 'is_mac', is_mac)
    monkeypatch.setattr(platform, 'is_windows', is_windows)

    assert next(iter(rendering.font_fallbacks()), None) == first


def _unknown_glyphs(text, font_name):
    import cairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo
    layout = PangoCairo.create_layout(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)))
    layout.set_text(text, -1)
    layout.set_font_description(Pango.FontDescription.from_string(font_name))
    return layout.get_unknown_glyphs_count()


@pytest.mark.skipif(not platform.is_mac, reason="macOS system UI font")
@pytest.mark.parametrize('text', ['सबै', 'ਸਾਰੇ', 'అన్నీ', 'ગુજરાતી', 'தமிழ்', 'മലയാളം', 'ଓଡ଼ିଆ'])
def test_macos_ui_font_renders_indic_scripts(text):
    # #4107: on macOS 26 Pango finds no font for these from
    # .AppleSystemUIFont alone; macOS 15 finds one by itself.
    assert _unknown_glyphs(text, rendering.with_font_fallbacks('.AppleSystemUIFont 13')) == 0


@pytest.mark.skipif(not platform.is_mac, reason="macOS system UI font")
def test_macos_ui_font_renders_gtks_ratio_sign():
    # #4465: GTK's catalogs write times as "15∶30" (U+2236 RATIO), which
    # macOS 15's UI font has no glyph for.
    assert _unknown_glyphs('15∶30', rendering.with_font_fallbacks('.AppleSystemUIFont 13')) == 0

@pytest.mark.skipif(not platform.is_windows, reason="Windows fonts")
@pytest.mark.parametrize('font', ['Segoe UI 10', 'Consolas 10'])
def test_windows_fonts_render_ethiopic(font):
    # #4208: Pango only falls back to a fixed list of Windows families.
    assert _unknown_glyphs('ሰላም', font) > 0
    assert _unknown_glyphs('ሰላም', rendering.with_font_fallbacks(font)) == 0


@pytest.mark.skipif(not platform.is_windows, reason="Windows fonts")
@pytest.mark.parametrize('font', ['Segoe UI 10', 'Consolas 10'])
@pytest.mark.parametrize('text', ['सबै', 'বাংলা', 'ਸਾਰੇ', 'සිංහල', 'అన్నీ', 'ไทย'])
def test_windows_fonts_render_indic_scripts_and_thai(font, text):
    # #4464: Pango's list names Indic fonts Windows no longer installs.
    assert _unknown_glyphs(text, rendering.with_font_fallbacks(font)) == 0
