#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Pango

from virtaal.common import pan_app

_font_descriptions = {}

def get_font_description(code):
    """Provide a Pango.FontDescription and keep it for reuse."""
    global _font_descriptions
    if not code in _font_descriptions:
        _font_descriptions[code] = Pango.FontDescription(code)
    return _font_descriptions[code]

def get_source_font_description():
    return get_font_description(pan_app.settings.language["sourcefont"])

def get_target_font_description():
    return get_font_description(pan_app.settings.language["targetfont"])

def get_role_font_description(role):
    if role == 'source':
        return get_source_font_description()
    elif role == 'target':
        return get_target_font_description()

def make_pango_layout(widget, text, width):
    pango_layout = Pango.Layout(widget.get_pango_context())
    pango_layout.set_width(width * Pango.SCALE)
    pango_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    pango_layout.set_text(text or "")
    return pango_layout


_languages = {}

def get_language(code):
    """Provide a Pango.Language and keep it for reuse."""
    global _languages
    if not code in _languages:
        _languages[code] = Pango.Language.from_string(code)
    return _languages[code]
