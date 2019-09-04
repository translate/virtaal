#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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
    pango_layout.set_text(text or u"")
    return pango_layout


_languages = {}

def get_language(code):
    """Provide a Pango.Language and keep it for reuse."""
    global _languages
    if not code in _languages:
        _languages[code] = Pango.Language.from_string(code)
    return _languages[code]
