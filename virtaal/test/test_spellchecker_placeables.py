#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The spell checker plugin with real GtkSpell on a real target text box."""

import gi
import pytest
from test_scaffolding import TestScaffolding
from translate.storage import factory

from virtaal.common import SignalTracker
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.plugins.spellchecker import Plugin

try:
    gi.require_version('GtkSpell', '3.0')
    import enchant
    from gi.repository import GtkSpell
except (ImportError, ValueError):
    GtkSpell = None


def _misspelled(textbox):
    tag = textbox.buffer.get_tag_table().lookup('gtkspell-misspelled')
    words, word = [], ''
    itr = textbox.buffer.get_start_iter()
    while not itr.is_end():
        if tag is not None and itr.has_tag(tag):
            word += itr.get_char()
        elif word:
            words.append(word)
            word = ''
        itr.forward_char()
    return words + [word] if word else words


@pytest.mark.skipif(GtkSpell is None or not enchant.dict_exists('en_US'),
                    reason='needs GtkSpell and an en_US dictionary')
class TestSpellCheckerPlaceables(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)

    def _checked_target(self, text, store="devsupport/testfiles/placeables.po", index=6):
        view = self.unit_controller.load_unit(factory.getobject(store).getunits()[index])
        textbox = view.targets[0]
        plugin = Plugin.__new__(Plugin)
        plugin._signal_tracker = SignalTracker()
        plugin._connect_to_textboxes(view, [textbox])
        if text is not None:
            textbox.set_text(text)
        checker = GtkSpell.Checker()
        checker.attach(textbox)
        checker.set_language('en_US')
        checker.recheck_all()
        return textbox, plugin, checker

    def teardown_method(self):
        self.plugin._signal_tracker.disconnect_all()
        self.checker.detach()

    def test_words_in_placeables_are_not_marked(self):
        # #4253
        textbox, self.plugin, self.checker = self._checked_target(
            '%(couXnt)s files renamd <b>bolld</b> &nbspp; {xyzzy}')

        assert _misspelled(textbox) == ['renamd', 'bolld', 'xyzzy']

    def test_words_typed_next_to_a_placeable_are_still_checked(self):
        textbox, self.plugin, self.checker = self._checked_target('%(count)s files')

        textbox.buffer.place_cursor(textbox.buffer.get_end_iter())
        textbox.buffer.insert_interactive_at_cursor(' renamd ', -1, True)

        assert _misspelled(textbox) == ['renamd']

    def test_text_inside_a_g_is_still_checked(self):
        textbox, self.plugin, self.checker = self._checked_target(
            None, store="devsupport/testfiles/placeables.xliff", index=0)
        textbox.buffer.place_cursor(textbox.buffer.get_iter_at_offset(8))
        textbox.buffer.insert_interactive_at_cursor('xq', -1, True)
        # GtkSpell leaves the word being typed alone.
        textbox.buffer.place_cursor(textbox.buffer.get_end_iter())
        self.checker.recheck_all()

        assert _misspelled(textbox) == ['hxqere']
