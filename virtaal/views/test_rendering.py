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


# Font fallbacks #

def test_font_fallbacks_keep_the_size_and_style(monkeypatch):
    monkeypatch.setattr(rendering, 'font_fallbacks', lambda: ('Ebrima',))

    assert rendering.with_font_fallbacks('Segoe UI Bold 13') == 'Segoe UI,Ebrima Bold 13'


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
