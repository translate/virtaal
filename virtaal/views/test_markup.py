#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for markuptext(), the function behind escape/XML/diff highlighting
in translation text - previously untested despite being used by
tmwidgets.py, storetreemodel.py, storecellrenderer.py and
label_expander.py. Uses the live current_theme colours for assertions
(rather than hardcoding hex codes) so these don't go stale if the theme's
palette changes."""

from virtaal.views.markup import markuptext
from virtaal.views.theme import current_theme


def test_markuptext_empty_returns_empty_string():
    assert markuptext("") == ""
    assert markuptext(None) == ""


def test_markuptext_escapes_ampersand_and_lt():
    assert markuptext("a & b < c") == "a &amp; b &lt; c"


def test_markuptext_marks_up_embedded_newline():
    result = markuptext("hello\nworld")
    subtle = current_theme['subtle_fg']
    assert result == 'hello<span foreground="%s">¶\n</span>world' % subtle


def test_markuptext_strips_trailing_newline_but_keeps_pilcrow():
    # A trailing newline's pilcrow is shown, but the newline itself isn't -
    # otherwise the markup would render an extra blank line.
    result = markuptext("trailing newline\n")
    subtle = current_theme['subtle_fg']
    assert result == 'trailing newline<span foreground="%s">¶</span>' % subtle
    assert not result.endswith("\n</span>")


def test_markuptext_markupescapes_false_leaves_newline_alone():
    result = markuptext("hello\nworld", markupescapes=False)
    assert result == "hello\nworld"
    assert "<span" not in result


def test_markuptext_marks_up_unusual_spaces():
    # Flagged: 2+ consecutive spaces anywhere, or 1+ leading/trailing.
    # Not flagged: a single space between words (the "double" here has two
    # spaces before it and after "lead" is a single one - not flagged).
    result = markuptext("  lead double  trail  ")
    assert result.count('<span underline="error" foreground="grey">') == 3
    # the actual space characters are preserved inside the markup, not lost
    assert result.replace('<span underline="error" foreground="grey">', "") \
                  .replace("</span>", "") == "  lead double  trail  "


def test_markuptext_fancyspaces_false_leaves_spaces_alone():
    result = markuptext("  lead double  trail  ", fancyspaces=False)
    assert result == "  lead double  trail  "
    assert "<span" not in result


def test_markuptext_uses_diff_markup_when_diff_text_differs():
    result = markuptext("hello world", diff_text="hello")
    insert_bg = current_theme['diff_insert_bg']
    assert insert_bg in result
    assert " world</span>" in result


def test_markuptext_ignores_diff_text_when_equal_to_text():
    # diff_text is only used when it differs from text - otherwise this is
    # a no-op plain escape, not a (pointless) self-diff.
    result = markuptext("same & same", diff_text="same & same")
    assert result == "same &amp; same"
    assert "<span" not in result
