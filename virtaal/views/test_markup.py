#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 Zuza Software Foundation
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

"""Tests for markuptext(), the function behind escape/XML/diff highlighting
in translation text - previously untested despite being used by
tmwidgets.py, storetreemodel.py, storecellrenderer.py and
label_expander.py. Uses the live current_theme colours for assertions
(rather than hardcoding hex codes) so these don't go stale if the theme's
palette changes."""

from virtaal.views.markup import markuptext
from virtaal.views.theme import current_theme


def test_markuptext_empty_returns_empty_string():
    assert markuptext(u"") == u""
    assert markuptext(None) == u""


def test_markuptext_escapes_ampersand_and_lt():
    assert markuptext(u"a & b < c") == u"a &amp; b &lt; c"


def test_markuptext_marks_up_embedded_newline():
    result = markuptext(u"hello\nworld")
    subtle = current_theme['subtle_fg']
    assert result == u'hello<span foreground="%s">¶\n</span>world' % subtle


def test_markuptext_strips_trailing_newline_but_keeps_pilcrow():
    # A trailing newline's pilcrow is shown, but the newline itself isn't -
    # otherwise the markup would render an extra blank line.
    result = markuptext(u"trailing newline\n")
    subtle = current_theme['subtle_fg']
    assert result == u'trailing newline<span foreground="%s">¶</span>' % subtle
    assert not result.endswith(u"\n</span>")


def test_markuptext_markupescapes_false_leaves_newline_alone():
    result = markuptext(u"hello\nworld", markupescapes=False)
    assert result == u"hello\nworld"
    assert u"<span" not in result


def test_markuptext_marks_up_unusual_spaces():
    # Flagged: 2+ consecutive spaces anywhere, or 1+ leading/trailing.
    # Not flagged: a single space between words (the "double" here has two
    # spaces before it and after "lead" is a single one - not flagged).
    result = markuptext(u"  lead double  trail  ")
    assert result.count(u'<span underline="error" foreground="grey">') == 3
    # the actual space characters are preserved inside the markup, not lost
    assert result.replace(u'<span underline="error" foreground="grey">', u"") \
                  .replace(u"</span>", u"") == u"  lead double  trail  "


def test_markuptext_fancyspaces_false_leaves_spaces_alone():
    result = markuptext(u"  lead double  trail  ", fancyspaces=False)
    assert result == u"  lead double  trail  "
    assert u"<span" not in result


def test_markuptext_uses_diff_markup_when_diff_text_differs():
    result = markuptext(u"hello world", diff_text=u"hello")
    insert_bg = current_theme['diff_insert_bg']
    assert insert_bg in result
    assert u" world</span>" in result


def test_markuptext_ignores_diff_text_when_equal_to_text():
    # diff_text is only used when it differs from text - otherwise this is
    # a no-op plain escape, not a (pointless) self-diff.
    result = markuptext(u"same & same", diff_text=u"same & same")
    assert result == u"same &amp; same"
    assert u"<span" not in result
