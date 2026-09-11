#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regression test for translate/virtaal#3329: Alt+Down on a plural
unit's second (or later) target copied the singular source instead of
the matching plural source form.
"""

from translate.misc.multistring import multistring

from virtaal.views.unitview import UnitView


class _FakeParent:
    def show_all(self):
        pass

    def hide_all(self):
        pass

    def hide(self):
        pass


class _FakeTextbox:
    def __init__(self, visible=True):
        self.props = type('_Props', (), {'visible': visible})()
        self.text = None
        self.selector_textboxes = None
        self.selector_textbox = None

    def modify_font(self, *_a):
        pass

    def set_text(self, text):
        self.text = text

    def get_parent(self):
        return _FakeParent()


class _FakeUnit:
    def __init__(self, target):
        # A real plural target (>1 form) is what actually matters here -
        # matches qm_compat.py's own real-world hasplural() shape,
        # where a .qm unit's single source never itself becomes a
        # multistring even when the target is genuinely plural.
        self.target = target

    def hasplural(self):
        return isinstance(self.target, multistring) and len(self.target.strings) > 1

    @property
    def rich_target(self):
        return list(self.target.strings) if isinstance(self.target, multistring) else [self.target]


def _make_view(source_forms, target):
    view = UnitView.__new__(UnitView)
    view._widgets = {
        'sources': [_FakeTextbox() for _ in source_forms],
        'targets': [_FakeTextbox() for _ in range(UnitView.MAX_TARGETS)],
    }
    view.unit = _FakeUnit(target)

    class _FakeLang:
        nplurals = len(target.strings) if isinstance(target, multistring) else 1

    class _FakeLangController:
        target_lang = _FakeLang()

    class _FakeMainController:
        lang_controller = _FakeLangController()

    view.controller = type('_C', (), {'main_controller': _FakeMainController()})()
    return view


def test_each_target_gets_its_own_matching_source_for_gettext_plurals():
    # Two real source forms (msgid, msgid_plural) - target[i]'s
    # selector_textbox should be sources[i], not always sources[0].
    view = _make_view(
        ['%d file', '%d files'],
        multistring(['form 0', 'form 1']))
    view._layout_update_targets()

    assert view.targets[0].selector_textbox is view.sources[0]
    assert view.targets[1].selector_textbox is view.sources[1]


def test_targets_fall_back_to_the_single_source_when_there_is_only_one():
    # .qm-style: one source covers every plural target form.
    view = _make_view(
        ['%n file(s) selected'],
        multistring(['form 0', 'form 1']))
    view._layout_update_targets()

    assert view.targets[0].selector_textbox is view.sources[0]
    assert view.targets[1].selector_textbox is view.sources[0]
