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

from types import SimpleNamespace

from translate.misc.multistring import multistring

from virtaal.views.unitview import UnitView


class _FakeParent:
    def show_all(self):
        pass

    def hide_all(self):
        pass

    def hide(self):
        pass


class _FakeStyleContext:
    def add_provider(self, *_a):
        pass


class _FakeTextbox:
    def __init__(self, visible=True):
        self.props = type('_Props', (), {'visible': visible})()
        self.text = None
        self.selector_textboxes = None
        self.selector_textbox = None

    def get_style_context(self):
        return _FakeStyleContext()

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


class _FakeMenuWidget:
    def __init__(self):
        self._sensitive = True

    def set_sensitive(self, value):
        self._sensitive = value

    def get_sensitive(self):
        return self._sensitive

    def connect(self, signal, handler):
        pass

    def set_accel_path(self, path):
        pass

    def set_accel_group(self, group):
        pass

    def get_accel_group(self):
        return None


class _FakeSetupMenusGui:
    def __init__(self):
        names = ('mnu_cut', 'mnu_copy', 'mnu_paste', 'mnu_placnext', 'mnu_placprev', 'mnu_transfer', 'menu_edit')
        self._widgets = {name: _FakeMenuWidget() for name in names}

    def get_object(self, name):
        return self._widgets[name]


class _FakeSetupMenusMainView:
    def __init__(self):
        self.gui = _FakeSetupMenusGui()

    def add_accel_group(self, group):
        pass

    def sync_menubar(self):
        pass


class _FakeSetupMenusStoreController:
    def connect(self, signal, handler):
        pass


def test_cut_copy_paste_disabled_before_any_store_event():
    # _set_menu_items_sensitive(False) (called right after this in the
    # real constructor) doesn't touch Cut/Copy/Paste - only the
    # store-closed handler does, and it's otherwise never called until
    # a real store-closed event fires, which never happens on a fresh
    # startup with no file ever opened.
    view = UnitView.__new__(UnitView)
    main_controller = type('_MC', (), {
        'view': _FakeSetupMenusMainView(),
        'store_controller': _FakeSetupMenusStoreController(),
    })()
    view.controller = type('_C', (), {'main_controller': main_controller})()

    view._setup_menus()

    assert not view.mnu_cut.get_sensitive()
    assert not view.mnu_copy.get_sensitive()
    assert not view.mnu_paste.get_sensitive()


class _FakeBuffer:
    def __init__(self):
        self.cut_calls = []
        self.copy_calls = []
        self.paste_calls = []

    def cut_clipboard(self, clipboard, default_editable):
        self.cut_calls.append(default_editable)

    def copy_clipboard(self, clipboard):
        self.copy_calls.append(clipboard)

    def paste_clipboard(self, clipboard, override_location, default_editable):
        self.paste_calls.append(default_editable)


class _FakeEditableTextbox:
    def __init__(self, focused=False):
        self._focused = focused
        self.buffer = _FakeBuffer()
        self.move_calls = []

    def is_focus(self):
        return self._focused

    def get_buffer(self):
        return self.buffer

    def move_elem_selection(self, direction):
        self.move_calls.append(direction)


def test_cut_cuts_from_the_focused_target_only():
    view = UnitView.__new__(UnitView)
    unfocused, focused = _FakeEditableTextbox(), _FakeEditableTextbox(focused=True)
    view._widgets = {'targets': [unfocused, focused], 'sources': []}

    view._on_cut(None)

    assert focused.buffer.cut_calls == [True]
    assert unfocused.buffer.cut_calls == []


def test_cut_does_nothing_when_no_target_is_focused():
    view = UnitView.__new__(UnitView)
    view._widgets = {'targets': [_FakeEditableTextbox()], 'sources': []}

    view._on_cut(None)  # must not raise


def test_copy_copies_from_a_focused_source_as_well_as_a_focused_target():
    view = UnitView.__new__(UnitView)
    focused_source = _FakeEditableTextbox(focused=True)
    view._widgets = {'targets': [_FakeEditableTextbox()], 'sources': [focused_source]}

    view._on_copy(None)

    assert len(focused_source.buffer.copy_calls) == 1


def test_paste_pastes_into_the_focused_target():
    view = UnitView.__new__(UnitView)
    focused = _FakeEditableTextbox(focused=True)
    view._widgets = {'targets': [focused], 'sources': []}

    view._on_paste(None)

    assert focused.buffer.paste_calls == [True]


def test_next_placeable_moves_selection_forward_on_the_focused_target():
    view = UnitView.__new__(UnitView)
    other, current = _FakeEditableTextbox(), _FakeEditableTextbox()
    view._widgets = {'targets': [other, current], 'sources': []}
    view._focused_target_n = 1

    view._on_next_placeable()

    assert current.move_calls == [1]
    assert other.move_calls == []


def test_prev_placeable_moves_selection_backward_on_the_focused_target():
    view = UnitView.__new__(UnitView)
    current, other = _FakeEditableTextbox(), _FakeEditableTextbox()
    view._widgets = {'targets': [current, other], 'sources': []}
    view._focused_target_n = 0

    view._on_prev_placeable()

    assert current.move_calls == [-1]


def test_transfer_copies_the_source_into_the_focused_target():
    view = UnitView.__new__(UnitView)
    focused = _FakeEditableTextbox(focused=True)
    view._widgets = {'targets': [focused], 'sources': []}
    copied = []
    view.copy_original = lambda textbox: copied.append(textbox)

    view._on_transfer()

    assert copied == [focused]


def test_store_loaded_enables_placeable_navigation_and_recomputes_edit_menu():
    view = UnitView.__new__(UnitView)
    view.mnu_next = _FakeMenuWidget()
    view.mnu_prev = _FakeMenuWidget()
    view.mnu_transfer = _FakeMenuWidget()
    view.mnu_cut = _FakeMenuWidget()
    view.mnu_copy = _FakeMenuWidget()
    view.mnu_paste = _FakeMenuWidget()
    view._widgets = {'targets': [], 'sources': []}

    view._on_store_loaded()

    assert view.mnu_next.get_sensitive()
    assert view.mnu_prev.get_sensitive()
    assert view.mnu_transfer.get_sensitive()
    # Nothing focused, so _update_edit_menu_sensitivity() disables all three.
    assert not view.mnu_cut.get_sensitive()
    assert not view.mnu_copy.get_sensitive()
    assert not view.mnu_paste.get_sensitive()


# _on_target_key_pressed() #

def _view_for_key_press():
    view = UnitView.__new__(UnitView)
    view.unit = object()
    return view


def test_on_target_key_pressed_with_no_eventname_falls_through():
    view = _view_for_key_press()

    assert view._on_target_key_pressed(None, None, '', None) is False


def test_on_target_key_pressed_enter_focuses_the_next_visible_target():
    view = _view_for_key_press()
    focused = []
    view.focus_text_view = lambda tb: focused.append(tb)
    next_textbox = SimpleNamespace(get_parent=lambda: SimpleNamespace(props=SimpleNamespace(visible=True)))

    result = view._on_target_key_pressed(None, None, 'enter', next_textbox)

    assert result is True
    assert focused == [next_textbox]


def test_on_target_key_pressed_ctrl_enter_advances_the_workflow_and_moves_on():
    view = _view_for_key_press()
    advanced = []
    view.advance_workflow_state = lambda direction: advanced.append(direction)
    key_press_calls = []
    view._on_key_press_event = lambda widget, event: key_press_calls.append(event)

    result = view._on_target_key_pressed(None, 'the-event', 'ctrl-enter', None)

    assert result is True
    assert advanced == [1]
    assert key_press_calls == ['the-event']


def test_on_target_key_pressed_ctrl_shift_enter_advances_the_workflow_backward():
    view = _view_for_key_press()
    advanced = []
    view.advance_workflow_state = lambda direction: advanced.append(direction)
    view._on_key_press_event = lambda widget, event: None

    result = view._on_target_key_pressed(None, 'the-event', 'ctrl-shift-enter', None)

    assert result is True
    assert advanced == [-1]


def test_on_target_key_pressed_alt_down_schedules_copy_original(monkeypatch):
    view = _view_for_key_press()
    scheduled = []
    monkeypatch.setattr('virtaal.views.unitview.GLib.idle_add', lambda func: scheduled.append(func))
    copied = []
    view.copy_original = lambda textbox: copied.append(textbox)
    textbox = object()

    result = view._on_target_key_pressed(textbox, None, 'alt-down', None)

    assert result is True
    assert len(scheduled) == 1
    scheduled[0]()  # run the deferred call as GLib would

    assert copied == [textbox]


def test_on_target_key_pressed_alt_down_skips_copy_if_the_unit_changed_first(monkeypatch):
    view = _view_for_key_press()
    scheduled = []
    monkeypatch.setattr('virtaal.views.unitview.GLib.idle_add', lambda func: scheduled.append(func))
    copied = []
    view.copy_original = lambda textbox: copied.append(textbox)

    view._on_target_key_pressed(object(), None, 'alt-down', None)
    view.unit = object()  # a different unit loaded before the idle callback runs
    scheduled[0]()

    assert copied == []


def test_on_target_key_pressed_shift_tab_moves_focus_back():
    view = _view_for_key_press()
    view._focused_target_n = 1
    focused = []
    view.focus_text_view = lambda tb: focused.append(tb)
    view._widgets = {'targets': ['t0', 't1'], 'sources': []}

    result = view._on_target_key_pressed(None, None, 'shift-tab', None)

    assert result is True
    # focused_target_n's setter delegates to focus_text_view(), which
    # (mocked here) is what actually updates _focused_target_n for real.
    assert focused == ['t0']


def test_on_target_key_pressed_shift_tab_does_nothing_at_the_first_target():
    view = _view_for_key_press()
    view._focused_target_n = 0
    focused = []
    view.focus_text_view = lambda tb: focused.append(tb)

    result = view._on_target_key_pressed(None, None, 'shift-tab', None)

    assert result is True
    assert view._focused_target_n == 0
    assert focused == []


def test_on_target_key_pressed_ctrl_tab_focuses_the_language_controller():
    view = _view_for_key_press()
    focused = []
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(view=SimpleNamespace(focus=lambda: focused.append(True))),
    ))

    result = view._on_target_key_pressed(None, None, 'ctrl-tab', None)

    assert result is True
    assert focused == [True]


def test_on_target_key_pressed_ctrl_shift_tab_focuses_the_mode_controller():
    view = _view_for_key_press()
    focused = []
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        mode_controller=SimpleNamespace(view=SimpleNamespace(focus=lambda: focused.append(True))),
    ))

    result = view._on_target_key_pressed(None, None, 'ctrl-shift-tab', None)

    assert result is True
    assert focused == [True]


def test_on_target_key_pressed_unrecognized_eventname_falls_through():
    view = _view_for_key_press()

    assert view._on_target_key_pressed(None, None, 'something-else', None) is False
