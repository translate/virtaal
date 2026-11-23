#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Patches for translate.storage.ts2: Qt length variants.

A Qt translation can hold several length variants, longest first:
<translation variants="yes"><lengthvariant>...</lengthvariant>...
(or the same inside each <numerusform> of a plural). tsunit reads such
a target as empty (only the whitespace between the variants), and
setting the target replaces every variant with one plain text
(translate/virtaal#4936).

Here a variants target reads as its first variant, and setting it
changes only the first variant's text, keeping the others."""

from lxml import etree
from translate.misc.multistring import multistring
from translate.misc.xml_helpers import safely_set_text
from translate.storage import ts2

_target = vars(ts2.tsunit).get('_virtaal_original_target', ts2.tsunit.target)


def _has_variants(node):
    return node.get('variants') == 'yes'


def _text(unit, node):
    if not _has_variants(node):
        return node.text or ''
    first = node.find(unit.namespaced('lengthvariant'))
    if first is None:
        return ''
    return first.text or ''


def _set_text(unit, node, text):
    if not _has_variants(node):
        safely_set_text(node, text or '')
        return
    first = node.find(unit.namespaced('lengthvariant'))
    if first is None:
        first = etree.SubElement(node, unit.namespaced('lengthvariant'))
    safely_set_text(first, text or '')


def _forms(unit, node):
    return node.findall(unit.namespaced('numerusform'))


def _get_target(self):
    node = self._gettargetnode()
    if self.hasplural():
        return multistring([_text(self, form) for form in _forms(self, node)])
    return _text(self, node)


def _set_target(self, target):
    node = self._gettargetnode()
    forms = _forms(self, node) if self.hasplural() else [node]
    if isinstance(target, multistring):
        strings = target.strings
    elif isinstance(target, list):
        strings = target
    else:
        strings = [target]
    if not any(_has_variants(form) for form in forms) or (
            not self.hasplural() and len(strings) > 1):
        _target.fset(self, target)
        return
    self._rich_target = None
    if self.target == target:
        return
    if not self.hasplural():
        _set_text(self, node, strings[0] if strings else '')
        return
    for form, string in zip(forms, strings):
        _set_text(self, form, string)
    for string in strings[len(forms):]:
        safely_set_text(etree.SubElement(node, self.namespaced('numerusform')), string or '')
    for form in forms[len(strings):]:
        node.remove(form)


ts2.tsunit.target = property(_get_target, _set_target)
ts2.tsunit._virtaal_original_target = _target
