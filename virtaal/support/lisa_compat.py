#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""translate-toolkit's LISA formats (TMX, XLIFF, TBX) set a new target
string as the target's leading text and keep its inline elements and
their tail text, so editing a TMX translation that starts with <ph/>
saved "Neu<ph/>Hallo Welt" (#4627). Here a changed target replaces the
whole content, and an unchanged one is left alone. Upstream bug; drop
this once translate-toolkit clears the children in settarget().

translate-toolkit's reindent() fails on a processing instruction inside
an element, so an XLIFF holding one couldn't be saved (#4727). Here it
leaves the instruction as it is, like a comment."""

from lxml import etree
from translate.misc import xml_helpers
from translate.storage import lisa


def _text_node(unit, lang, use_lang):
    if use_lang and lang is not None:
        node = unit._get_target_language_node(lang)
    else:
        node = unit.target_dom
    if node is not None and unit.textNode:
        node = next(node.iter(unit.namespaced(unit.textNode)), node)
    return node


def _patch(unit_class, use_lang):
    settarget = unit_class.settarget

    def compat_settarget(self, target, lang=None if use_lang else "xx", append=False):
        if target is not None and not append:
            current = self.gettarget(lang) if use_lang and lang is not None else self.target
            if current == target:
                # translate-toolkit 3.18+ rewrites an unchanged target too.
                self._rich_target = None
                return
            node = _text_node(self, lang, use_lang)
            if node is not None:
                for child in list(node):
                    node.remove(child)
        settarget(self, target, lang, append)

    compat_settarget.ttk_settarget = settarget
    unit_class.settarget = compat_settarget


_patch(lisa.LISAunit, use_lang=False)
# translate-toolkit 3.18+ (3.17.5 is the Python 3.10 pin): TMX units
# find their target by language.
if hasattr(lisa, "MultilingualLISAunit"):
    _patch(lisa.MultilingualLISAunit, use_lang=True)


_reindent = xml_helpers.reindent


def reindent(elem, *args, **kwargs):
    if elem.tag is etree.PI:
        return
    _reindent(elem, *args, **kwargs)


reindent.ttk_reindent = _reindent
# reindent() recurses through xml_helpers' global; lisa imports it by name.
xml_helpers.reindent = lisa.reindent = reindent
