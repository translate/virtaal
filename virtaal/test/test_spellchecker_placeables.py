#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The spell checker plugin with real GtkSpell on a real target text box."""

from types import SimpleNamespace

import gi
import pytest
from gi.repository import GObject
from test_scaffolding import TestScaffolding
from translate.storage import factory

from virtaal.common import SignalTracker
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.plugins import spellchecker
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


class _UnitView(GObject.Object):
    """A unit view that hasn't made its text boxes yet."""
    __gsignals__ = {
        'sources-created': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        'targets-created': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        'textview-language-changed': (GObject.SignalFlags.RUN_FIRST, None, (object, object)),
    }

    def __init__(self):
        super().__init__()
        self.sources = []
        self.targets = []


@pytest.mark.skipif(GtkSpell is None or not enchant.dict_exists('en_US'),
                    reason='needs GtkSpell and an en_US dictionary')
class TestSpellCheckerPlaceables(TestScaffolding):
    plugin = checker = None

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
        if self.plugin is not None:
            self.plugin._signal_tracker.disconnect_all()
        if self.checker is not None:
            self.checker.detach()
        self.plugin = self.checker = None

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

    def _start(self, monkeypatch, main_controller):
        idle = []
        monkeypatch.setattr(spellchecker.GLib, 'idle_add', lambda func, *args, **kwargs: idle.append((func, args)))
        plugin = Plugin('spellchecker', main_controller)
        for func, args in idle:
            func(*args)
        return plugin

    def test_starting_checks_each_text_box_in_its_language(self, monkeypatch):
        view = self.unit_controller.load_unit(factory.getobject("devsupport/testfiles/placeables.po").getunits()[6])
        monkeypatch.setattr(self.lang_controller, '_source_lang', SimpleNamespace(code='en'))
        monkeypatch.setattr(self.lang_controller, '_target_lang', SimpleNamespace(code='xx'))

        plugin = self._start(monkeypatch, self.main_controller)
        try:
            for source in view.sources:
                assert source.spell_lang == 'en_US'
                assert GtkSpell.Checker.get_from_text_view(source).get_language() == 'en_US'
            for target in view.targets:
                assert target.spell_lang is None
                assert GtkSpell.Checker.get_from_text_view(target) is None
        finally:
            plugin.destroy()

        assert all(GtkSpell.Checker.get_from_text_view(source) is None for source in view.sources)

    def test_text_boxes_made_after_starting_are_checked(self, monkeypatch):
        view = self.unit_controller.load_unit(factory.getobject("devsupport/testfiles/placeables.po").getunits()[6])
        textbox = view.targets[0]
        unit_view = _UnitView()
        main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=unit_view), lang_controller=self.lang_controller)
        self.plugin = self._start(monkeypatch, main_controller)

        unit_view.emit('targets-created', [textbox])
        textbox.set_text('%(couXnt)s files renamd')
        self.checker = GtkSpell.Checker()
        self.checker.attach(textbox)
        self.checker.set_language('en_US')
        self.checker.recheck_all()

        assert _misspelled(textbox) == ['renamd']
