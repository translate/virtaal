#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk, Pango

from virtaal.views.widgets.cellrendererwidget import CellRendererWidget, CellWidget
from virtaal.views.widgets.selectview import SelectView


def _rectangle(width=10, height=10):
    return SimpleNamespace(x=0, y=0, width=width, height=height)


def _toplevel_widget():
    win = Gtk.OffscreenWindow()
    win.set_default_size(400, 300)
    box = Gtk.Box()
    win.add(box)
    win.show_all()
    return box


# __init__() #

def test_init_sets_defaults():
    renderer = CellRendererWidget(strfunc=lambda w: '')

    assert renderer.default_width == -1
    assert renderer.widget is None
    assert renderer.widget_func(None) is None
    assert renderer.props.mode == Gtk.CellRendererMode.EDITABLE


def test_init_keeps_a_custom_default_width_and_widget_func():
    widget_func = lambda item: item
    renderer = CellRendererWidget(strfunc=lambda w: '', default_width=123, widget_func=widget_func)

    assert renderer.default_width == 123
    assert renderer.widget_func is widget_func


# do_set_property() / do_get_property() #

def test_widget_property_roundtrips_via_the_gobject_property_interface():
    renderer = CellRendererWidget(strfunc=lambda w: '')
    obj = object()

    renderer.props.widget = obj

    assert renderer.props.widget is obj
    assert renderer.widget is obj


# do_get_size() #

def test_do_get_size_with_a_cell_area_returns_a_padded_rect():
    renderer = CellRendererWidget(strfunc=lambda w: '')

    x, y, width, height = renderer.do_get_size(None, _rectangle(100, 50))

    assert (x, y, width, height) == (2, 2, 96, 46)


def test_do_get_size_without_a_cell_area_measures_the_layout_text():
    renderer = CellRendererWidget(strfunc=lambda w: 'hello')
    widget = _toplevel_widget()

    _x, _y, width, height = renderer.do_get_size(widget, None)

    assert width > CellRendererWidget.XPAD * 2
    assert height > CellRendererWidget.YPAD * 2


def test_do_get_size_falls_back_to_default_width_for_an_unallocated_widget():
    renderer = CellRendererWidget(strfunc=lambda w: 'hi', default_width=250)
    widget = Gtk.Box()  # never added to a shown window - allocation stays 0

    _x, _y, width, _height = renderer.do_get_size(widget, None)

    # default_width (250) is what gets passed as the wrap width, so the
    # single short word here fits on one line well short of it.
    assert width < 250


def test_do_get_size_grows_to_fit_a_larger_embedded_widget():
    renderer = CellRendererWidget(strfunc=lambda w: 'hi')
    widget = _toplevel_widget()
    # An unrealized widget's size_request() reports 0 regardless of an
    # explicit set_size_request() - needs a shown OffscreenWindow.
    renderer.widget = _toplevel_widget()
    renderer.widget.set_size_request(300, 150)

    _x, _y, width, height = renderer.do_get_size(widget, None)

    assert width >= 300 + CellRendererWidget.XPAD * 2
    assert height >= 150 + CellRendererWidget.YPAD * 2


# do_render() #

def test_do_render_skips_a_selected_row_already_being_edited(monkeypatch):
    renderer = CellRendererWidget(strfunc=lambda w: 'hi')
    # 'editing' is a read-only GObject property on the base class,
    # normally flipped by GTK's own treeview machinery - stand in a
    # plain object to force the branch under test.
    renderer.props = SimpleNamespace(editing=True)
    calls = []
    monkeypatch.setattr(Gtk, 'render_layout', lambda **kwargs: calls.append(kwargs))
    widget = _toplevel_widget()

    renderer.do_render(object(), widget, _rectangle(), _rectangle(), Gtk.CellRendererState.SELECTED)

    assert calls == []


def test_do_render_paints_the_layout_when_not_editing(monkeypatch):
    renderer = CellRendererWidget(strfunc=lambda w: 'hi')
    calls = []
    monkeypatch.setattr(Gtk, 'render_layout', lambda **kwargs: calls.append(kwargs))
    widget = _toplevel_widget()

    renderer.do_render(object(), widget, _rectangle(), _rectangle(100, 50), Gtk.CellRendererState(0))

    assert len(calls) == 1
    assert calls[0]['x'] == CellRendererWidget.XPAD


# do_start_editing() #

def _select_view_with(item):
    return SelectView(items=[item])


def test_do_start_editing_returns_none_without_a_widget():
    renderer = CellRendererWidget(strfunc=lambda w: '', widget_func=lambda item: None)
    sview = _select_view_with({'name': 'A', 'enabled': True, 'data': 'a'})

    result = renderer.do_start_editing(None, sview, '0', None, None, Gtk.CellRendererState(0))

    assert result is None


def test_do_start_editing_returns_none_without_a_config_entry():
    renderer = CellRendererWidget(strfunc=lambda w: '', widget_func=lambda item: Gtk.Label())
    sview = _select_view_with({'name': 'A', 'enabled': True, 'data': 'a'})

    result = renderer.do_start_editing(None, sview, '0', None, None, Gtk.CellRendererState(0))

    assert result is None


def test_do_start_editing_wraps_the_widget_in_a_shown_cell_widget():
    made = Gtk.Label()
    renderer = CellRendererWidget(strfunc=lambda w: '', widget_func=lambda item: made)
    sview = _select_view_with({'name': 'A', 'enabled': True, 'data': 'a',
                                'config': lambda parent: None})

    result = renderer.do_start_editing(None, sview, '0', None, None, Gtk.CellRendererState(0))

    assert isinstance(result, CellWidget)
    assert made in result.get_children()
    assert made.get_visible()


# create_pango_layout() #

def test_create_pango_layout_sets_the_markup_text():
    renderer = CellRendererWidget(strfunc=lambda w: '')
    widget = _toplevel_widget()

    layout = renderer.create_pango_layout('<b>hi</b>', widget, 100)

    assert layout.get_text() == 'hi'


def test_create_pango_layout_right_aligns_for_rtl():
    renderer = CellRendererWidget(strfunc=lambda w: '')
    widget = _toplevel_widget()
    widget.set_direction(Gtk.TextDirection.RTL)

    layout = renderer.create_pango_layout('hi', widget, 100)

    assert layout.get_alignment() == Pango.Alignment.RIGHT


# CellWidget #

def test_cell_widget_packs_its_widgets():
    label = Gtk.Label()

    cell_widget = CellWidget(label)

    assert label in cell_widget.get_children()


def test_cell_widget_detaches_a_widget_from_its_existing_parent():
    label = Gtk.Label()
    old_parent = Gtk.Box()
    old_parent.add(label)

    CellWidget(label)

    assert label.get_parent() is not old_parent


def test_cell_widget_interface_stubs_are_callable():
    cell_widget = CellWidget()

    assert cell_widget.do_editing_done() is None
    assert cell_widget.do_remove_widget() is None
    assert cell_widget.do_start_editing() is None
