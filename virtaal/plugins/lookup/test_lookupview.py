#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk, Pango

from virtaal.plugins.lookup.lookupview import LookupView
from virtaal.views.widgets.wordatcursor import WordAtCursorSelector


class _FakeIter:
    def inside_word(self):
        return False


class _FakeBuffer:
    def __init__(self, text):
        self._text = text

    def get_has_selection(self):
        return bool(self._text)

    def get_selection_bounds(self):
        return (0, len(self._text), False)

    def get_text(self, *args, **kwargs):
        return self._text

    def get_insert(self):
        # Only reached when get_has_selection() is already False -
        # select_word_at_cursor() only needs inside_word() to decide
        # there's nothing to select.
        return None

    def get_iter_at_mark(self, mark):
        return _FakeIter()


class _FakeTextbox:
    def __init__(self, text, role='source'):
        self.buffer = _FakeBuffer(text)
        self.role = role


class _FakeLang:
    code = 'en'


class _FakeLangController:
    source_lang = _FakeLang()
    target_lang = _FakeLang()


class _FakeTopLevelModel:
    TOP_LEVEL = True

    def create_menu_items(self, *args):
        item = Gtk.MenuItem(label='Synonyms')
        submenu = Gtk.Menu()
        submenu.append(Gtk.MenuItem(label='sukmana'))
        item.set_submenu(submenu)
        return [item]


class _FakeNestedModel:
    TOP_LEVEL = False

    def create_menu_items(self, *args):
        item = Gtk.MenuItem(label='Google')
        return [item]


class _FakePluginController:
    def __init__(self, plugins):
        self.plugins = plugins


class _FakeController:
    def __init__(self, plugins):
        self.plugin_controller = _FakePluginController(plugins)


def _make_view(plugins):
    view = LookupView.__new__(LookupView)
    view.controller = _FakeController(plugins)
    view.lang_controller = _FakeLangController()
    view._word_selector = WordAtCursorSelector()
    return view


def test_top_level_model_items_with_a_submenu_show_their_children():
    view = _make_view({'thesaurus': _FakeTopLevelModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox('word'), menu)

    synonyms_item = next(i for i in menu.get_children() if i.get_label() == 'Synonyms')
    assert synonyms_item.get_submenu() is not None
    assert all(child.get_visible() for child in synonyms_item.get_submenu().get_children())


def test_top_level_model_items_go_directly_into_the_context_menu():
    # A thesaurus result is specific enough that nesting it one level
    # deeper, alongside unrelated web look-ups, would just make it
    # slower to reach - unlike weblookup, it sits as its own entry.
    view = _make_view({'thesaurus': _FakeTopLevelModel(), 'weblookup': _FakeNestedModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox('word'), menu)

    top_level_labels = [i.get_label() for i in menu.get_children() if isinstance(i, Gtk.MenuItem) and i.get_label()]
    assert 'Synonyms' in top_level_labels
    assert 'Google' not in top_level_labels


def test_nested_model_items_stay_under_the_look_up_submenu():
    view = _make_view({'weblookup': _FakeNestedModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox('word'), menu)

    lookup_item = next(i for i in menu.get_children() if isinstance(i, Gtk.MenuItem) and i.get_submenu())
    submenu_labels = [i.get_label() for i in lookup_item.get_submenu().get_children()]
    assert submenu_labels == ['Google']


def test_populate_popup_does_nothing_without_a_selection():
    view = _make_view({'thesaurus': _FakeTopLevelModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox(''), menu)

    assert menu.get_children() == []


def test_populate_popup_ellipsizes_a_long_selection():
    view = _make_view({'weblookup': _FakeNestedModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox('a' * 60), menu)

    item = next(i for i in menu.get_children() if isinstance(i, Gtk.MenuItem) and i.get_submenu())
    assert item.get_label() == 'Look-up "%s"' % ('a' * 60)
    label_widget = item.get_child()
    assert label_widget.get_ellipsize() == Pango.EllipsizeMode.MIDDLE
    assert label_widget.get_max_width_chars() == 40


class _RealTextbox:
    """A real Gtk.TextBuffer, not a fake - GTK's own word-boundary
    logic (inside_word()/starts_word()/ends_word()) is exactly what's
    under test here, not worth reimplementing in a fake."""

    def __init__(self, text, cursor_offset, role='source'):
        self.buffer = Gtk.TextBuffer()
        self.buffer.set_text(text)
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(cursor_offset))
        self.role = role


def test_populate_popup_selects_the_word_under_the_cursor_when_nothing_is_selected():
    # A plain right-click (nothing dragged out first) shouldn't
    # require selecting a word first - the spell checker's own
    # right-click suggestions already work this way.
    view = _make_view({'thesaurus': _FakeTopLevelModel()})
    menu = Gtk.Menu()
    textbox = _RealTextbox('The quick brown fox', cursor_offset=6)

    view._on_populate_popup(textbox, menu)

    start, end = textbox.buffer.get_selection_bounds()
    assert textbox.buffer.get_text(start, end, False) == 'quick'
    assert menu.get_children() != []


def test_populate_popup_does_nothing_when_the_cursor_is_not_inside_a_word():
    view = _make_view({'thesaurus': _FakeTopLevelModel()})
    menu = Gtk.Menu()
    textbox = _RealTextbox('The quick brown fox', cursor_offset=3)

    view._on_populate_popup(textbox, menu)

    assert not textbox.buffer.get_has_selection()
    assert menu.get_children() == []
