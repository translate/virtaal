#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gdk, Gtk
from test_scaffolding import TestScaffolding
from translate.storage import factory
from translate.storage.placeables.strelem import StringElem

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views.placeablesguiinfo import (
    BxGUI,
    ExGUI,
    GPlaceableGUI,
    NewlineGUI,
    StringElemGUI,
    UnknownXMLGUI,
    UrlGUI,
    XPlaceableGUI,
    _count_anchors,
    update_style,
)

PLACEABLES_PO = "devsupport/testfiles/placeables.po"
PLACEABLES_XLIFF = "devsupport/testfiles/placeables.xliff"


def _fake_textbox(role='source'):
    """A real Gtk.TextView stands in for a TextBox - StringElemGUI only
    ever needs .buffer/.role/.get_pango_context()/.add_child_at_anchor()
    from it, all of which a plain TextView already provides."""
    tb = Gtk.TextView()
    tb.role = role
    tb.buffer = tb.get_buffer()
    return tb


# StringElemGUI.__init__ #

def test_init_rejects_a_non_stringelem():
    with pytest.raises(ValueError):
        StringElemGUI(elem='not a StringElem', textbox=_fake_textbox())


def test_init_accepts_fg_bg_cursor_allowed_overrides():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox(), fg='#123456', bg='#abcdef', cursor_allowed=False)

    assert gui.fg == '#123456'
    assert gui.bg == '#abcdef'
    assert gui.cursor_allowed is False


def test_init_ignores_an_unrecognised_kwarg():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox(), bogus='ignored')

    assert not hasattr(gui, 'bogus')


# create_tags() #

def test_create_tags_with_string_colors():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox(), fg='#ff0000', bg='#00ff00')

    [(tag, start, end)] = gui.create_tags()

    assert start is None and end is None
    assert tag.props.foreground_rgba.to_string() == 'rgb(255,0,0)'
    assert tag.props.background_rgba.to_string() == 'rgb(0,255,0)'


def test_create_tags_with_rgba_colors():
    fg, bg = Gdk.RGBA(), Gdk.RGBA()
    fg.parse('#ff0000')
    bg.parse('#00ff00')
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox(), fg=fg, bg=bg)

    [(tag, _start, _end)] = gui.create_tags()

    assert tag.props.foreground_rgba.to_string() == 'rgb(255,0,0)'
    assert tag.props.background_rgba.to_string() == 'rgb(0,255,0)'


def test_create_tags_skips_falsy_colors():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox(), fg=None, bg=None)

    [(tag, _start, _end)] = gui.create_tags()

    assert tag.props.foreground_set is False
    assert tag.props.background_set is False


# create_repr_widgets() / copy() / get_insert_widget() / has_*_widget() #

def test_base_create_repr_widgets_adds_no_widgets():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox())

    assert gui.widgets == []


def test_copy_preserves_style_and_target():
    elem = StringElem('hi')
    textbox = _fake_textbox()
    gui = StringElemGUI(elem=elem, textbox=textbox, fg='#111', bg='#222', cursor_allowed=False)

    copied = gui.copy()

    assert copied is not gui
    assert copied.elem is elem
    assert copied.textbox is textbox
    assert copied.fg == '#111'
    assert copied.bg == '#222'
    assert copied.cursor_allowed is False


def test_get_insert_widget_is_none_by_default():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox())

    assert gui.get_insert_widget() is None


def test_has_start_and_end_widget_are_false_with_no_widgets():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox())

    assert gui.has_start_widget() is False
    assert gui.has_end_widget() is False


def test_has_start_and_end_widget_reflect_the_widgets_list():
    gui = StringElemGUI(elem=StringElem('hi'), textbox=_fake_textbox())
    gui.widgets = [Gtk.Label(), Gtk.Label()]

    assert gui.has_start_widget()
    assert gui.has_end_widget()


# _count_anchors() #

def test_count_anchors_counts_child_anchors_before_the_iter():
    buffer = Gtk.TextBuffer()
    buffer.set_text('ab')
    buffer.create_child_anchor(buffer.get_iter_at_offset(1))

    assert _count_anchors(buffer, buffer.get_iter_at_offset(0)) == 0
    assert _count_anchors(buffer, buffer.get_iter_at_offset(2)) == 1


# Real rendering, via a real PlaceablesController and the placeables.po/xliff fixtures #

class TestRealPlaceableRendering(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        self.po_store = factory.getobject(PLACEABLES_PO)
        self.xliff_store = factory.getobject(PLACEABLES_XLIFF)

    def _target_for(self, store, source_text):
        unit = next(u for u in store.getunits() if u.source == source_text)
        for textbox in self.unit_controller.view.targets:
            textbox._suggestion = None
        view = self.unit_controller.load_unit(unit)
        return view.targets[0]

    def _source_for(self, store, source_text):
        unit = next(u for u in store.getunits() if u.source == source_text)
        view = self.unit_controller.load_unit(unit)
        return view.sources[0]

    def test_length_matches_the_rendered_text_length(self):
        textbox = self._target_for(self.po_store, '%s files copied')

        assert textbox.elem.gui_info.length() == len('%s files copied')

    def test_render_produces_a_pilcrow_widget_for_a_newline(self):
        textbox = self._target_for(self.po_store, 'First line.\nSecond line.')

        newline_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, NewlineGUI))

        assert len(newline_elem.gui_info.widgets) == 1
        assert newline_elem.gui_info.widgets[0].get_label() == '¶'

    def test_render_applies_the_url_tag_to_a_url(self):
        # UrlPlaceable is deliberately excluded from target text (URLs
        # stay source-only) - use the source textbox instead.
        textbox = self._source_for(self.po_store, 'See https://virtaal.org for details.')

        url_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, UrlGUI))
        [(tag, _start, _end)] = url_elem.gui_info.create_tags()

        assert tag.props.underline == 1  # Pango.Underline.SINGLE

    def test_gui_to_tree_index_matches_when_there_are_no_widgets(self):
        textbox = self._target_for(self.po_store, '%s files copied')

        assert textbox.elem.gui_info.gui_to_tree_index(5) == 5

    def test_tree_to_gui_index_roundtrips_through_treeindex_to_iter(self):
        textbox = self._target_for(self.po_store, '%s files copied')

        assert textbox.elem.gui_info.tree_to_gui_index(3) == 3

    def test_iter_sub_with_index_yields_each_child_with_its_offset(self):
        textbox = self._target_for(self.po_store, '%s files copied')

        pairs = list(textbox.elem.gui_info.iter_sub_with_index())

        assert [offset for _child, offset in pairs] == [0, 2]

    def test_index_finds_a_childs_offset(self):
        textbox = self._target_for(self.po_store, '%s files copied')
        placeable = next(e for e in textbox.elem.depth_first() if e.__class__ not in textbox.unselectables)

        assert textbox.elem.gui_info.index(placeable) == 0

    def test_elem_at_offset_finds_the_placeable_at_its_own_position(self):
        textbox = self._target_for(self.po_store, '%s files copied')
        placeable = next(e for e in textbox.elem.depth_first() if e.__class__ not in textbox.unselectables)

        assert textbox.elem.gui_info.elem_at_offset(0) is placeable

    def test_elem_at_offset_returns_none_out_of_range(self):
        textbox = self._target_for(self.po_store, '%s files copied')

        assert textbox.elem.gui_info.elem_at_offset(-1) is None
        assert textbox.elem.gui_info.elem_at_offset(999) is None

    def test_g_placeable_wraps_its_content_in_bracket_widgets(self):
        textbox = self._target_for(self.xliff_store, 'Click here to continue.')

        g_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, GPlaceableGUI))

        assert len(g_elem.gui_info.widgets) == 2
        assert g_elem.gui_info.widgets[0].get_label() == '<1|'
        assert g_elem.gui_info.widgets[1].get_label() == '>'

    def test_x_placeable_is_a_single_standalone_widget(self):
        textbox = self._target_for(self.xliff_store, 'A line breakafter it.')

        x_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, XPlaceableGUI))

        assert len(x_elem.gui_info.widgets) == 1
        assert x_elem.gui_info.widgets[0].get_label() == '[2]'

    def test_bx_and_ex_placeables_bracket_editable_text(self):
        textbox = self._target_for(self.xliff_store, 'Some bold text.')

        bx_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, BxGUI))
        ex_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, ExGUI))

        assert bx_elem.gui_info.widgets[0].get_label() == '(('
        assert ex_elem.gui_info.widgets[0].get_label() == '))'

    def test_unknown_xml_placeable_shows_its_tag_name(self):
        textbox = self._target_for(self.xliff_store, 'A placeholder: CODE here.')

        ph_elem = next(e for e in textbox.elem.depth_first() if isinstance(e.gui_info, UnknownXMLGUI))

        assert ph_elem.gui_info.widgets[0].get_label() == '{ph|'
        assert ph_elem.gui_info.widgets[1].get_label() == '}'


# update_style() #

def test_update_style_sets_the_base_class_colours_from_the_widget():
    widget = Gtk.Label()
    window = Gtk.Window()
    window.add(widget)
    window.show_all()

    update_style(widget)

    assert StringElemGUI.fg
    assert StringElemGUI.bg
    window.destroy()
