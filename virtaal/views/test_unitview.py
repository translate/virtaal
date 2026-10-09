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

import pytest
from gi.repository import Gdk, Gtk
from translate.misc.multistring import multistring
from translate.storage.placeables import general, parse
from translate.storage.placeables.strelem import StringElem

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
        names = ('mnu_cut', 'mnu_copy', 'mnu_paste', 'mnu_placnext', 'mnu_placprev', 'mnu_transfer',
                 'mnu_placinsert', 'menu_edit')
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
    def __init__(self, has_selection=True):
        self.has_selection = has_selection
        self.cut_calls = []
        self.copy_calls = []
        self.paste_calls = []

    def cut_clipboard(self, clipboard, default_editable):
        self.cut_calls.append(default_editable)

    def copy_clipboard(self, clipboard):
        self.copy_calls.append(clipboard)

    def get_has_selection(self):
        return self.has_selection

    def paste_clipboard(self, clipboard, override_location, default_editable):
        self.paste_calls.append(default_editable)


class _FakeEditableTextbox:
    def __init__(self, focused=False, has_selection=True, text='', selector_textbox=None):
        self._focused = focused
        self.buffer = _FakeBuffer(has_selection)
        self.move_calls = []
        self._text = text
        self.selector_textbox = selector_textbox or self

    def get_text(self):
        return self._text

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


class _FakeClipboard:
    def __init__(self):
        self.texts = []

    def set_text(self, text, length):
        self.texts.append(text)


def test_copy_with_nothing_selected_copies_the_source(monkeypatch):
    clipboard = _FakeClipboard()
    monkeypatch.setattr('virtaal.views.unitview.Gtk.Clipboard.get', lambda selection: clipboard)
    view = UnitView.__new__(UnitView)
    source = _FakeEditableTextbox(text='%s files copied')
    target = _FakeEditableTextbox(focused=True, has_selection=False, selector_textbox=source)
    view._widgets = {'targets': [target], 'sources': [source]}

    view._on_copy(None)

    assert clipboard.texts == ['%s files copied']
    assert target.buffer.copy_calls == []


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


def _placeable_menu_view(sources):
    view = UnitView.__new__(UnitView)
    view.mnu_next = _FakeMenuWidget()
    view.mnu_prev = _FakeMenuWidget()
    view.mnu_transfer = _FakeMenuWidget()
    view.mnu_insert = _FakeMenuWidget()
    view.mnu_cut = _FakeMenuWidget()
    view.mnu_copy = _FakeMenuWidget()
    view.mnu_paste = _FakeMenuWidget()
    view._widgets = {'targets': [], 'sources': sources}
    return view


def _placeable_source(elems, visible=True):
    parent = SimpleNamespace(props=SimpleNamespace(visible=visible))
    return SimpleNamespace(selectable_elems=lambda: elems, get_parent=lambda: parent)


def test_store_loaded_enables_transfer_and_recomputes_edit_menu():
    view = _placeable_menu_view([])

    view._on_store_loaded()

    assert view.mnu_transfer.get_sensitive()
    # No sources yet, so no placeables to navigate or insert.
    assert not view.mnu_next.get_sensitive()
    assert not view.mnu_prev.get_sensitive()
    assert not view.mnu_insert.get_sensitive()
    # Nothing focused, so _update_edit_menu_sensitivity() disables all three.
    assert not view.mnu_cut.get_sensitive()
    assert not view.mnu_copy.get_sensitive()
    assert not view.mnu_paste.get_sensitive()


def test_placeable_menu_disabled_when_source_has_no_placeables():
    view = _placeable_menu_view([_placeable_source([])])

    view._update_placeable_menu_sensitivity()

    assert not view.mnu_next.get_sensitive()
    assert not view.mnu_prev.get_sensitive()
    assert not view.mnu_insert.get_sensitive()


def test_placeable_menu_enabled_when_source_has_placeables():
    view = _placeable_menu_view([_placeable_source(['%s'])])
    for widget in (view.mnu_next, view.mnu_prev, view.mnu_insert):
        widget.set_sensitive(False)

    view._update_placeable_menu_sensitivity()

    assert view.mnu_next.get_sensitive()
    assert view.mnu_prev.get_sensitive()
    assert view.mnu_insert.get_sensitive()


def test_placeable_menu_ignores_hidden_sources():
    # A hidden plural source keeps the previous unit's text.
    view = _placeable_menu_view([_placeable_source([]), _placeable_source(['%s'], visible=False)])

    view._update_placeable_menu_sensitivity()

    assert not view.mnu_next.get_sensitive()
    assert not view.mnu_insert.get_sensitive()


def test_copy_stays_enabled_with_nothing_selected():
    # Copy with nothing selected copies the source (#3963).
    view = UnitView.__new__(UnitView)
    view.mnu_cut = _FakeMenuWidget()
    view.mnu_copy = _FakeMenuWidget()
    view.mnu_paste = _FakeMenuWidget()
    target = _FakeEditableTextbox(focused=True, has_selection=False)
    view._widgets = {'targets': [target], 'sources': []}

    view._update_edit_menu_sensitivity()

    assert view.mnu_copy.get_sensitive()
    assert not view.mnu_cut.get_sensitive()


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


def test_on_target_key_pressed_alt_down_schedules_insert_placeable(monkeypatch):
    view = _view_for_key_press()
    scheduled = []
    monkeypatch.setattr('virtaal.views.unitview.GLib.idle_add', lambda func: scheduled.append(func))
    copied = []
    view.insert_placeable = lambda textbox: copied.append(textbox)
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


# is_modified() / get_target_n() / set_target_n() #

def test_is_modified_reflects_the_modified_flag():
    view = UnitView.__new__(UnitView)
    view._modified = True

    assert view.is_modified() is True


def test_get_target_n_returns_the_textboxs_text():
    view = UnitView.__new__(UnitView)
    tb = _FakeTextbox()
    tb.get_text = lambda: 'hello'
    view._widgets = {'targets': [tb]}

    assert view.get_target_n(0) == 'hello'


def test_set_target_n_sets_text_without_moving_the_cursor_by_default():
    view = UnitView.__new__(UnitView)
    tb = _FakeTextbox()
    view._widgets = {'targets': [tb]}

    view.set_target_n(0, 'hello')

    assert tb.text == 'hello'


def test_set_target_n_places_the_cursor_when_a_position_is_given():
    view = UnitView.__new__(UnitView)
    buf = Gtk.TextBuffer()
    buf.set_text('hello')
    placed = []
    tb = _FakeTextbox()
    tb.buffer = SimpleNamespace(
        place_cursor=lambda it: placed.append(it.get_offset()),
        get_iter_at_offset=lambda offset: buf.get_iter_at_offset(offset),
    )
    view._widgets = {'targets': [tb]}

    view.set_target_n(0, 'hello', cursor_pos=3)

    assert tb.text == 'hello'
    assert placed == [3]


# insert_placeable() #

class _FakeSource:
    def __init__(self, elems):
        self._elems = elems
        self.selected_elem = None

    def select_first_elem(self):
        if self._elems and self.selected_elem is None:
            self.selected_elem = self._elems[0]


def _insert_placeable_target(source, deferred=False):
    inserted, moved = [], []
    textbox = SimpleNamespace(
        selector_textbox=source,
        insert_translation=lambda elem: inserted.append(elem) or not deferred,
        move_elem_selection=moved.append,
    )
    return textbox, inserted, moved


def test_insert_placeable_inserts_the_selected_placeable_and_moves_on():
    source = _FakeSource(['first', 'second'])
    source.selected_elem = 'second'
    textbox, inserted, moved = _insert_placeable_target(source)

    UnitView.__new__(UnitView).insert_placeable(textbox)

    assert inserted == ['second']
    assert moved == [1]


def test_insert_placeable_selects_the_first_placeable_when_none_is_selected():
    textbox, inserted, moved = _insert_placeable_target(_FakeSource(['first', 'second']))

    UnitView.__new__(UnitView).insert_placeable(textbox)

    assert inserted == ['first']


def test_insert_placeable_does_nothing_without_placeables():
    # Alt+Down no longer falls back to copying the whole source.
    textbox, inserted, moved = _insert_placeable_target(_FakeSource([]))

    UnitView.__new__(UnitView).insert_placeable(textbox)

    assert inserted == []
    assert moved == []


def test_insert_placeable_keeps_the_selection_while_a_candidate_is_chosen():
    # #962: the source selection moved on as soon as the term list opened.
    source = _FakeSource(['term'])
    textbox, inserted, moved = _insert_placeable_target(source, deferred=True)

    UnitView.__new__(UnitView).insert_placeable(textbox)

    assert inserted == ['term']
    assert moved == []


def test_select_first_placeables_skips_hidden_targets():
    view = UnitView.__new__(UnitView)
    visible_source, hidden_source = _FakeSource(['a']), _FakeSource(['b'])
    parent = lambda visible: SimpleNamespace(props=SimpleNamespace(visible=visible))
    view._widgets = {'targets': [
        SimpleNamespace(selector_textbox=visible_source, get_parent=lambda: parent(True)),
        SimpleNamespace(selector_textbox=hidden_source, get_parent=lambda: parent(False)),
    ]}

    view.select_first_placeables()

    assert visible_source.selected_elem == 'a'
    assert hidden_source.selected_elem is None


# copy_original() #

def _copy_original_view(source_text, target_lang_code, role='target'):
    view = UnitView.__new__(UnitView)
    view._get_editing_start_pos = lambda elem: 0
    undo_calls = []
    placeables_controller = SimpleNamespace(
        get_parsers_for_textbox=lambda tb: [],
        apply_parsers=lambda elem, parsers: None,
        non_target_placeables=[],
    )
    main_controller = SimpleNamespace(
        undo_controller=SimpleNamespace(push_current_text=undo_calls.append),
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(code=target_lang_code)),
        placeables_controller=placeables_controller,
    )
    view.controller = SimpleNamespace(main_controller=main_controller)
    view.unit = SimpleNamespace(rich_source=[StringElem(source_text)])

    source_textbox = SimpleNamespace(selected_elem=None)
    set_calls, refresh_calls = [], []
    textbox = SimpleNamespace(
        selector_textbox=source_textbox,
        selector_textboxes=[source_textbox],
        role=role,
        elem=None,
        set_text=lambda tgt: set_calls.append(str(tgt)),
        refresh=lambda: refresh_calls.append(True),
    )
    return view, textbox, undo_calls, set_calls, refresh_calls


def test_copy_original_copies_the_source_verbatim_when_punctuation_is_unaffected():
    view, textbox, undo_calls, set_calls, refresh_calls = _copy_original_view('Hello world', 'en')

    view.copy_original(textbox)

    assert set_calls == ['Hello world']
    assert len(undo_calls) == 1
    assert refresh_calls == [True]


def test_copy_original_applies_punctuation_translation_when_it_differs():
    view, textbox, undo_calls, set_calls, refresh_calls = _copy_original_view('Hello: world', 'fr')

    view.copy_original(textbox)

    assert set_calls == ['Hello: world', 'Hello\xa0: world']
    assert len(undo_calls) == 2
    assert refresh_calls == [True]


# do_start_editing() #

def test_do_start_editing_focuses_the_first_target():
    view = UnitView.__new__(UnitView)
    view._widgets = {'targets': ['t0', 't1']}
    focused = []
    view.focus_text_view = focused.append

    view.do_start_editing()

    assert focused == ['t0']


# load_unit() #

def test_load_unit_does_nothing_when_the_same_unit_is_already_loaded():
    view = UnitView.__new__(UnitView)
    unit = object()
    view.unit = unit
    view._update_editor_gui = lambda: pytest.fail('must not rebuild the editor for the same unit')

    view.load_unit(unit)  # must not raise


# update_languages() / _update_textview_language() #

class _FakePangoContext:
    def __init__(self):
        self.language = None
        self.font_description = None

    def set_language(self, lang):
        self.language = lang

    def set_font_description(self, desc):
        self.font_description = desc


def test_update_languages_applies_fonts_and_languages_to_sources_and_targets():
    view = UnitView.__new__(UnitView)
    pango_ctx_src = _FakePangoContext()
    pango_ctx_tgt = _FakePangoContext()
    src = _FakeTextbox()
    src.get_pango_context = lambda: pango_ctx_src
    tgt = _FakeTextbox()
    tgt.get_pango_context = lambda: pango_ctx_tgt
    view._widgets = {'sources': [src], 'targets': [tgt]}
    emitted = []
    view.emit = lambda signal, *args: emitted.append((signal, args))
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(
            source_lang=SimpleNamespace(code='en'),
            target_lang=SimpleNamespace(code='fr'),
        )))

    view.update_languages()

    assert pango_ctx_src.language is not None
    assert pango_ctx_tgt.language is not None
    assert pango_ctx_tgt.font_description is not None
    assert ('textview-language-changed', (src, 'en')) in emitted
    assert ('textview-language-changed', (tgt, 'fr')) in emitted


# _create_workflow_liststore() #

def test_create_workflow_liststore_returns_an_empty_store_without_a_workflow():
    view = UnitView.__new__(UnitView)
    view.controller = SimpleNamespace(current_unit=SimpleNamespace(_workflow=None))

    lst = view._create_workflow_liststore()

    assert len(lst) == 0


# _layout_update_notes() #

def test_layout_update_notes_truncates_a_long_translator_comment():
    view = UnitView.__new__(UnitView)
    label = SimpleNamespace(texts=[])
    label.set_text = label.texts.append
    label.show_all = lambda: None
    label.hide = lambda: None
    view._widgets = {'notes': {'translator': label}}
    long_comment = 'x' * 250
    view.unit = SimpleNamespace(getnotes=lambda origin: long_comment, getlocations=lambda: [])

    view._layout_update_notes('translator')

    assert label.texts == [long_comment[:200] + '...']


# _layout_update_sources() / _layout_update_targets() - unit-is-None branch #

def test_layout_update_sources_hides_extra_boxes_when_no_unit_is_loaded():
    view = UnitView.__new__(UnitView)
    view._create_sources = lambda: None
    src0, src1 = _FakeTextbox(), _FakeTextbox()
    parent0, parent1 = SimpleNamespace(shown=[]), SimpleNamespace(hidden=[])
    parent0.show = lambda: parent0.shown.append(True)
    parent1.hide_all = lambda: parent1.hidden.append(True)
    src0.get_parent = lambda: parent0
    src1.get_parent = lambda: parent1
    view._widgets = {'sources': [src0, src1]}
    view.unit = None

    view._layout_update_sources()

    assert src0.text == ''
    assert parent0.shown == [True]
    assert parent1.hidden == [True]


def test_layout_update_targets_hides_extra_boxes_when_no_unit_is_loaded():
    view = UnitView.__new__(UnitView)
    view._create_targets = lambda: None
    tgt0, tgt1 = _FakeTextbox(), _FakeTextbox()
    parent0, parent1 = SimpleNamespace(shown=[]), SimpleNamespace(hidden=[])
    parent0.show_all = lambda: parent0.shown.append(True)
    parent1.hide_all = lambda: parent1.hidden.append(True)
    tgt0.get_parent = lambda: parent0
    tgt1.get_parent = lambda: parent1
    view._widgets = {'targets': [tgt0, tgt1]}
    view.unit = None

    view._layout_update_targets()

    assert tgt0.text == ''
    assert parent0.shown == [True]
    assert parent1.hidden == [True]


# _layout_update_states() / advance_workflow_state() / update_state() #

def test_layout_update_states_hides_the_state_widget_without_any_state_names():
    view = UnitView.__new__(UnitView)
    widget = SimpleNamespace(hidden=[])
    widget.hide = lambda: widget.hidden.append(True)
    view._widgets = {'state': widget}
    view.controller = SimpleNamespace(get_unit_state_names=lambda: {})
    view.unit = SimpleNamespace(STATE=True)

    view._layout_update_states()

    assert widget.hidden == [True]


def test_layout_update_states_names_the_icon_only_state_buttons():
    # The arrow buttons have no label, so GTK gives them no accessible name
    view = UnitView.__new__(UnitView)
    view._widgets = {'state': None, 'vbox_right': Gtk.VBox()}
    view.controller = SimpleNamespace(get_unit_state_names=lambda: {})
    view.unit = SimpleNamespace(STATE=True)

    view._layout_update_states()

    statenav = view._widgets['state']
    assert statenav.btn_back.get_accessible().get_name() == 'Previous state'
    assert statenav.btn_forward.get_accessible().get_name() == 'Next state'


def test_advance_workflow_state_does_nothing_without_a_stateful_unit():
    view = UnitView.__new__(UnitView)
    view.unit = SimpleNamespace(STATE=False)
    view._widgets = {'state': SimpleNamespace(move_state=lambda offset: pytest.fail('must not move state'))}

    view.advance_workflow_state(1)  # must not raise


def test_update_state_selects_by_name():
    view = UnitView.__new__(UnitView)
    selected = []
    view._widgets = {'state': SimpleNamespace(select_by_name=selected.append)}

    view.update_state('translated')

    assert selected == ['translated']


# _on_state_changed() #

def test_on_state_changed_updates_workflow_state_and_marks_modified():
    view = UnitView.__new__(UnitView)
    calls = []
    view.controller = SimpleNamespace(
        current_unit=SimpleNamespace(_workflow=True),
        set_current_state=lambda newstate, from_user: calls.append((newstate, from_user)),
    )
    view.modified = lambda: calls.append('modified')

    view._on_state_changed(None, 'reviewed')

    assert calls == [('reviewed', True), 'modified']


def test_on_state_changed_skips_setting_state_without_a_workflow():
    view = UnitView.__new__(UnitView)
    calls = []
    view.controller = SimpleNamespace(current_unit=SimpleNamespace(_workflow=None))
    view.modified = lambda: calls.append('modified')

    view._on_state_changed(None, 'reviewed')

    assert calls == ['modified']


# _on_key_press_event() #

def test_on_key_press_event_resets_must_advance_for_a_non_enter_key():
    view = UnitView.__new__(UnitView)
    view.must_advance = True

    result = view._on_key_press_event(None, SimpleNamespace(keyval=Gdk.KEY_a))

    assert result is False
    assert view.must_advance is False


# _on_target_changed() #

def test_on_target_changed_writes_a_plain_string_target_and_marks_modified():
    view = UnitView.__new__(UnitView)
    tb = _FakeTextbox()
    tb.elem = None
    tb.get_text = lambda: 'hello'
    view._widgets = {'targets': [tb]}
    view.unit = SimpleNamespace(hasplural=lambda: False, target=None)
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(nplurals=1))))
    modified_calls = []
    view.modified = lambda: modified_calls.append(True)

    view._on_target_changed(None, 0)

    assert view.unit.target == 'hello'
    assert modified_calls == [True]


def test_on_target_changed_raises_for_a_nonzero_index_on_a_non_plural_unit():
    view = UnitView.__new__(UnitView)
    tb = _FakeTextbox()
    tb.elem = None
    tb.get_text = lambda: 'hello'
    view._widgets = {'targets': [None, tb]}
    view.unit = SimpleNamespace(hasplural=lambda: False)
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(nplurals=1))))
    view.modified = lambda: None

    with pytest.raises(IndexError):
        view._on_target_changed(None, 1)


def test_on_target_changed_pads_and_writes_a_plural_target():
    view = UnitView.__new__(UnitView)
    tb = _FakeTextbox()
    tb.elem = None
    tb.get_text = lambda: 'two'
    view._widgets = {'targets': [None, tb]}
    view.unit = SimpleNamespace(hasplural=lambda: True, target=SimpleNamespace(strings=['one']))
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(nplurals=3))))
    modified_calls = []
    view.modified = lambda: modified_calls.append(True)

    view._on_target_changed(None, 1)

    assert view.unit.target == ['one', 'two', '']
    assert modified_calls == [True]


def test_on_target_changed_writes_a_placeable_element_and_marks_modified():
    view = UnitView.__new__(UnitView)
    elem = object()
    tb = _FakeTextbox()
    tb.elem = elem
    view._widgets = {'targets': [tb]}
    view.unit = SimpleNamespace(hasplural=lambda: False, rich_target=[None])
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(nplurals=1))))
    modified_calls = []
    view.modified = lambda: modified_calls.append(True)

    view._on_target_changed(None, 0)

    assert view.unit.rich_target == [elem]
    assert modified_calls == [True]


def test_on_target_changed_pads_a_plural_rich_target_before_writing_the_element():
    view = UnitView.__new__(UnitView)
    elem = object()
    tb = _FakeTextbox()
    tb.elem = elem
    view._widgets = {'targets': [None, tb]}
    view.unit = SimpleNamespace(hasplural=lambda: True, rich_target=['one'])
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(nplurals=3))))
    modified_calls = []
    view.modified = lambda: modified_calls.append(True)

    view._on_target_changed(None, 1)

    assert view.unit.rich_target == ['one', elem, '']
    assert modified_calls == [True]


# _on_textbox_paste_clipboard() / _on_textbox_focused() / _on_textbox_unfocused() #

def test_on_textbox_paste_clipboard_emits_paste_start_with_offsets():
    view = UnitView.__new__(UnitView)
    buf = Gtk.TextBuffer()
    buf.set_text('hello world')
    buf.place_cursor(buf.get_iter_at_offset(5))
    textbox = SimpleNamespace(buffer=buf, get_text=lambda: 'hello world')
    emitted = []
    view.emit = lambda signal, *args: emitted.append((signal, args))

    view._on_textbox_paste_clipboard(textbox, 2)

    assert emitted == [('paste-start', ('hello world', {'insert_offset': 5, 'selection_offset': 5}, 2))]


def test_on_textbox_focused_recomputes_edit_menu_sensitivity():
    view = UnitView.__new__(UnitView)
    calls = []
    view._update_edit_menu_sensitivity = lambda: calls.append('focused')

    view._on_textbox_focused(None, None)

    assert calls == ['focused']


def test_on_textbox_unfocused_recomputes_edit_menu_sensitivity():
    view = UnitView.__new__(UnitView)
    calls = []
    view._update_edit_menu_sensitivity = lambda: calls.append('unfocused')

    view._on_textbox_unfocused(None, None)

    assert calls == ['unfocused']


# _on_target_populate_popup(): right-click "Placeables" submenu

class _FakeSourceTextbox:
    unselectables = [StringElem]

    def __init__(self, text):
        self.elem = parse(text, general.parsers)


class _FakeTargetTextbox:
    def __init__(self, source_textbox):
        self.selector_textbox = source_textbox
        self.inserted = []

    def insert_translation(self, elem):
        self.inserted.append(elem)


def _make_popup_view():
    view = UnitView.__new__(UnitView)
    non_target_placeables = [general.UrlPlaceable]
    placeables_controller = type('_PC', (), {'non_target_placeables': non_target_placeables})()
    main_controller = type('_MC', (), {'placeables_controller': placeables_controller})()
    view.controller = type('_C', (), {'main_controller': main_controller})()
    return view


def _submenu_labels(menu):
    for item in menu.get_children():
        if item.get_submenu() is not None:
            return [i.get_label() for i in item.get_submenu().get_children()]
    return None


def test_populate_popup_lists_every_recognised_source_placeable():
    view = _make_popup_view()
    source = _FakeSourceTextbox('Save %s files now')
    target = _FakeTargetTextbox(source)
    menu = Gtk.Menu()

    view._on_target_populate_popup(target, menu)

    assert _submenu_labels(menu) == ['%s']


def test_populate_popup_excludes_non_target_placeables():
    # URLs stay source-only - matches copy_original()'s own filtering.
    view = _make_popup_view()
    source = _FakeSourceTextbox('Save %s files at https://example.com now')
    target = _FakeTargetTextbox(source)
    menu = Gtk.Menu()

    view._on_target_populate_popup(target, menu)

    assert _submenu_labels(menu) == ['%s']


def test_populate_popup_adds_nothing_when_the_source_has_no_placeables():
    view = _make_popup_view()
    source = _FakeSourceTextbox('Just plain text, nothing to offer')
    target = _FakeTargetTextbox(source)
    menu = Gtk.Menu()

    view._on_target_populate_popup(target, menu)

    assert menu.get_children() == []


def test_populate_popup_item_inserts_the_placeable_on_activate():
    view = _make_popup_view()
    source = _FakeSourceTextbox('Save %s files now')
    target = _FakeTargetTextbox(source)
    menu = Gtk.Menu()

    view._on_target_populate_popup(target, menu)
    for item in menu.get_children():
        if item.get_submenu() is not None:
            item.get_submenu().get_children()[0].activate()

    assert len(target.inserted) == 1
    assert str(target.inserted[0]) == '%s'
