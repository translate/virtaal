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

from gi.repository import Gtk
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
