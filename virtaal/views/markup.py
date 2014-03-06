#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2011 Zuza Software Foundation
# Copyright 2014 F Wolff
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

import re

from diff_match_patch import diff_match_patch

from virtaal.views.theme import current_theme


# We want to draw unexpected spaces specially so that users can spot them
# easily without having to resort to showing all spaces weirdly
_fancy_spaces_re = re.compile(r"""(?m)  #Multiline expression
        [ ]{2,}|     #More than two consecutive
        ^[ ]+|       #At start of a line
        [ ]+$        #At end of line""", re.VERBOSE)
"""A regular expression object to find all unusual spaces we want to show"""

def _fancyspaces(string):
    """Indicate the fancy spaces with a grey squigly."""
    spaces = string.group()
#    while spaces[0] in "\t\n\r":
#        spaces = spaces[1:]
    return u'<span underline="error" foreground="grey">%s</span>' % spaces


# Highligting for XML

# incorrect XML might be marked up incorrectly:  "<a> text </a more text bla"
_xml_re = re.compile("&lt;[^>]+>")
def _fancy_xml(escape):
    """Marks up the XML to appear in the warning red colour."""
    return u'<span foreground="%s">%s</span>' % (current_theme['markup_warning_fg'], escape.group())

def _subtle_escape(escape):
    """Marks up the given escape to appear in a subtle grey colour."""
    return u'<span foreground="%s">%s</span>' % (current_theme['subtle_fg'], escape)

def _escape_entities(s):
    """Escapes '&' and '<' in literal text so that they are not seen as markup."""
    s = s.replace(u"&", u"&amp;") # Must be done first!
    s = s.replace(u"<", u"&lt;")
    s = _xml_re.sub(_fancy_xml, s)
    return s


# Public methods

def markuptext(text, fancyspaces=True, markupescapes=True, diff_text=u""):
    """Markup the given text to be pretty Pango markup.

    Special characters (&, <) are converted, XML markup highligthed with
    escapes and unusual spaces optionally being indicated."""
    # locations are coming through here for some reason - tooltips, maybe
    if not text:
        return u""

    if diff_text and diff_text != text:
        text = pango_diff(diff_text, text)
    else:
        text = _escape_entities(text)

    if fancyspaces:
        text = _fancy_spaces_re.sub(_fancyspaces, text)

    if markupescapes:
#        text = text.replace(u"\r\n", _subtle_escape(u'¶\r\n')
        text = text.replace(u"\n", _subtle_escape(u'¶\n'))
        if text.endswith(u'\n</span>'):
            text = text[:-len(u'\n</span>')] + u'</span>'

    return text

def escape(text):
    """This is to escape text for use with gtk.TextView"""
    if not text:
        return ""
    text = text.replace("\n", u'¶\n')
    if text.endswith("\n"):
        text = text[:-len("\n")]
    return text

def unescape(text):
    """This is to unescape text for use with gtk.TextView"""
    if not text:
        return ""
    text = text.replace("\t", "")
    text = text.replace("\n", "")
    text = text.replace("\r", "")
    text = text.replace("\\t", "\t")
    text = text.replace("\\n", "\n")
    text = text.replace("\\r", "\r")
    text = text.replace("\\\\", "\\")
    return text


def _pango_spans(attr, text):
    return "<span %s>%s</span>" % (attr, _escape_entities(text))


# Templates for pango markup
# Variable substitution is done later, so that it can react to theme changes.
_diff_pango_templates = {
        'insert_attr':
                "underline='single'"\
                "underline_color='#777777'"\
                "weight='bold'"\
                "background='%(diff_insert_bg)s'",
        'delete_attr':
                "strikethrough='true'"\
                "strikethrough_color='#777'"\
                "background='%(diff_delete_bg)s'",
        #replace_attr_remove = delete_attr
        'replace_attr_add':
                "underline='single'"\
                "underline_color='#777777'"\
                "weight='bold'"
                "background='%(diff_replace_bg)s'",
        'replace_attr_add_case':
                "underline='single'"\
                "underline_color='#777777'"\
                "background='%(diff_replace_bg)s'",
}

differencer = diff_match_patch()
def pango_diff(a, b):
    """Highlights the differences between a and b for Pango rendering.

    We try to simplify things by only showing the new part of a replacement,
    unless it might be misleading (e.g. when a big chunk is replaced with a
    much shorter string). Certain cases with mostly case differences are
    highlighted more subtly."""

    insert_attr = _diff_pango_templates['insert_attr'] % current_theme
    delete_attr = _diff_pango_templates['delete_attr'] % current_theme
    replace_attr_remove = delete_attr
    replace_attr_add = _diff_pango_templates['replace_attr_add'] % current_theme
    replace_attr_add_case = _diff_pango_templates['replace_attr_add_case'] % current_theme

    textdiff = u"" # to store the final result
    removed = u"" # the removed text that we might still want to add
    diff = differencer.diff_main(a, b)
    differencer.diff_cleanupSemantic(diff)
    for op, text in diff:
        if op == 0: # equality
            if removed:
                textdiff += _pango_spans(delete_attr, removed)
                removed = u""
            textdiff += _escape_entities(text)
        elif op == 1: # insertion
            if removed:
                # this is part of a substitution, not a plain insertion. We
                # will format this differently.
                len_text = len(text)
                len_removed = len(removed)
                # if the new insertion is big enough (will draw attention) or
                # the removed part is not much bigger than the insertion we
                # can give a subtle highlighting for mostly case differences:
                if (len_text > 5 or len_removed < len_text + 2) and \
                        removed.lower().endswith(text.lower()):
                    # a more subtle replace highligting, since only case differs
                    textdiff += _pango_spans(replace_attr_add_case, text)
                else:
                    # Replacement. We only show the deleted part of the
                    # replacement if it is much longer than the new insertion
                    # and not alphanumeric (to draw attention):
                    if len_text < 3 and len_removed > 2 * len_text and \
                            not removed.isalpha():
                        textdiff += _pango_spans(delete_attr, removed)
                    textdiff += _pango_spans(replace_attr_add, text)
                removed = u""
            else:
                # plain insertion
                textdiff += _pango_spans(insert_attr, text)
        elif op == -1: # deletion
            removed = text
    if removed:
        textdiff += _pango_spans(delete_attr, removed)
    return textdiff
