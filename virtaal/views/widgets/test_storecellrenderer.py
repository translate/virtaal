#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import cairo
import pytest
from gi.repository import Gtk
from translate.storage.placeables import StringElem

from virtaal.views import rendering
from virtaal.views.placeablesguiinfo import NewlineGUI
from virtaal.views.widgets.storecellrenderer import (
    StoreCellRenderer,
    compute_optimal_height,
)


def test_compute_optimal_height_unregistered_type_raises():
    with pytest.raises(NotImplementedError):
        compute_optimal_height(object(), 100)


def test_compute_optimal_height_widget_is_a_noop():
    # Gtk.Widget itself is abstract - Gtk.Separator is a plain concrete
    # widget with no more specific registration of its own, so it
    # dispatches to the Gtk.Widget handler.
    widget = Gtk.Separator()
    compute_optimal_height(widget, 100)  # must not raise


def test_compute_optimal_height_label_sets_size_request():
    label = Gtk.Label(label='hello')
    compute_optimal_height(label, 200)

    assert label.get_size_request() == (200, label.get_size_request()[1])
    assert label.get_size_request()[1] > 0


def _realized_textview(text, pilcrows=0):
    """A real, off-screen-rendered Gtk.TextView with `text` as its
    content - optionally with `pilcrows` real NewlineGUI pilcrow
    widgets (the actual production class, not a stand-in - its
    deliberately-small size_request, smaller than a line of text, is
    exactly what makes this bug real), one inserted before each of
    `text`'s first `pilcrows` newlines."""
    win = Gtk.OffscreenWindow()
    textview = Gtk.TextView()
    textview.role = 'target'
    # unitview.py sets this on every real textview regardless of
    # placeables - without it, a NewlineGUI's own font override (it
    # sets the same font, but only as a side effect of existing) makes
    # a with-pilcrow textview measure in a different font than a plain
    # one, comparing two fonts' line heights instead of the
    # placeable's actual contribution.
    rendering.set_widget_font(textview, rendering.get_target_font_description())
    textview.get_pango_context().set_font_description(rendering.get_target_font_description())
    buf = textview.get_buffer()
    remaining = pilcrows
    while remaining and '\n' in text:
        before, text = text.split('\n', 1)
        buf.insert(buf.get_end_iter(), before)
        widget = NewlineGUI(StringElem('\n'), textview).widgets[0]
        anchor = buf.create_child_anchor(buf.get_end_iter())
        textview.add_child_at_anchor(widget, anchor)
        widget.show()
        buf.insert(buf.get_end_iter(), '\n')
        remaining -= 1
    buf.insert(buf.get_end_iter(), text)
    win.add(textview)
    win.show_all()
    return textview


def test_compute_optimal_height_textview_matches_a_plain_two_line_estimate():
    textview = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(textview, 200)

    assert textview.get_parent().get_size_request()[1] > 0


def test_compute_optimal_height_textview_accounts_for_an_embedded_placeable_widget():
    # The plain-text Pango layout compute_optimal_height() builds its
    # estimate from has no idea about child-anchor widgets (e.g. the
    # pilcrow standing in for a newline) - those take real vertical
    # space this text-only estimate doesn't, undercounting the row
    # height needed and clipping the wrapped line below the widget
    # (#3536).
    plain = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(plain, 200)
    plain_height = plain.get_parent().get_size_request()[1]

    with_pilcrow = _realized_textview('First line.\nSecond line.', pilcrows=1)
    compute_optimal_height(with_pilcrow, 200)
    pilcrow_height = with_pilcrow.get_parent().get_size_request()[1]

    assert pilcrow_height > plain_height


def test_compute_optimal_height_does_not_fully_stack_multiple_embedded_widgets():
    # A unit with several placeables needs a bit more real room than
    # one with a single one, but nowhere near each widget's full own
    # height added on top of the others - a four-pilcrow unit came out
    # roughly four times taller than it needed to be before this.
    text = 'One.\nTwo.\nThree.\nFour.'
    plain = _realized_textview(text)
    compute_optimal_height(plain, 200)
    plain_height = plain.get_parent().get_size_request()[1]

    pilcrow_holder = _realized_textview('\n', pilcrows=1)
    pilcrow_natural_height = pilcrow_holder.get_children()[0].get_preferred_height()[1]

    three_pilcrows = _realized_textview(text, pilcrows=3)
    compute_optimal_height(three_pilcrows, 200)
    three_pilcrows_height = three_pilcrows.get_parent().get_size_request()[1]

    assert plain_height < three_pilcrows_height < plain_height + 3 * pilcrow_natural_height


def test_compute_optimal_height_reflects_a_reused_widgets_new_content():
    # A unit switch reuses the same editor widget - the old anchor
    # widget is destroyed and a new one created for the new unit's
    # content, so this must look at the widget's current children each
    # time, not anything cached from an earlier call.
    textview = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(textview, 200)
    plain_height = textview.get_parent().get_size_request()[1]

    buf = textview.get_buffer()
    buf.set_text('First line.')
    widget = NewlineGUI(StringElem('\n'), textview).widgets[0]
    anchor = buf.create_child_anchor(buf.get_end_iter())
    textview.add_child_at_anchor(widget, anchor)
    widget.show()
    buf.insert(buf.get_end_iter(), '\nSecond line.')
    compute_optimal_height(textview, 200)
    pilcrow_height = textview.get_parent().get_size_request()[1]

    assert pilcrow_height > plain_height


def test_compute_optimal_height_container_skips_invisible_children():
    box = Gtk.Box()
    box.set_visible(True)
    visible_label = Gtk.Label(label='visible')
    visible_label.set_visible(True)
    hidden_label = Gtk.Label(label='hidden')
    hidden_label.set_visible(False)
    box.add(visible_label)
    box.add(hidden_label)

    compute_optimal_height(box, 200)

    assert visible_label.get_size_request()[0] == 200
    assert hidden_label.get_size_request() == (-1, -1)


def _rectangle(width=10, height=10):
    return SimpleNamespace(x=0, y=0, width=width, height=height)


def _blank_pixel(fuzzy, flags):
    """Paint into a fresh transparent surface and return its first
    pixel - non-zero means something was actually painted there."""
    renderer = StoreCellRenderer(None)
    renderer.unit = SimpleNamespace(isfuzzy=lambda: fuzzy)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
    cr = cairo.Context(surface)

    renderer._paint_fuzzy_background_if_selected(cr, _rectangle(), flags)

    surface.flush()
    return bytes(surface.get_data()[:4])


def test_paints_fuzzy_background_when_selected():
    # GTK only honours cell_background while a row isn't selected - the
    # selection highlight otherwise unconditionally replaces it,
    # hiding the fuzzy indicator on exactly the rows a translator is
    # most likely to have selected (#3321).
    assert _blank_pixel(fuzzy=True, flags=Gtk.CellRendererState.SELECTED) != b'\x00\x00\x00\x00'


def test_does_not_paint_when_not_selected():
    # GTK's own cell_background already handles this case correctly.
    assert _blank_pixel(fuzzy=True, flags=Gtk.CellRendererState(0)) == b'\x00\x00\x00\x00'


def test_does_not_paint_a_selected_non_fuzzy_row():
    assert _blank_pixel(fuzzy=False, flags=Gtk.CellRendererState.SELECTED) == b'\x00\x00\x00\x00'


# compute_optimal_height() - remaining dispatch branches #

def test_compute_optimal_height_invisible_container_is_a_noop():
    box = Gtk.Box()
    box.set_visible(False)
    label = Gtk.Label(label='hidden')
    box.add(label)

    compute_optimal_height(box, 200)  # must not raise, and must not touch label

    assert label.get_size_request() == (-1, -1)


def test_compute_optimal_height_grid_only_recomputes_its_vbox_middle_child():
    grid = Gtk.Grid()
    middle = Gtk.Label(label='middle')
    middle.set_name('vbox_middle')
    other = Gtk.Label(label='other')
    other.set_name('not_middle')
    grid.attach(middle, 0, 0, 1, 1)
    grid.attach(other, 1, 0, 1, 1)

    compute_optimal_height(grid, 200)

    assert middle.get_size_request()[0] == 100  # width / 2
    assert other.get_size_request() == (-1, -1)


def test_compute_optimal_height_invisible_textview_is_a_noop():
    textview = Gtk.TextView()
    textview.set_visible(False)
    box = Gtk.Box()
    box.add(textview)

    compute_optimal_height(textview, 200)  # must not raise

    assert box.get_size_request() == (-1, -1)


def test_compute_optimal_height_textview_falls_back_to_source_text_when_buffer_is_empty():
    # An empty buffer (nothing typed yet) still needs a real height
    # estimate - based on the *source* text's own length (adjusted for
    # the target language), since that's the best guess of how much
    # room the eventual translation will need.
    textview = _realized_textview('')
    textview._source_text = 'A reasonably long source sentence.'

    compute_optimal_height(textview, 200)

    assert textview.get_parent().get_size_request()[1] > 0


def test_compute_optimal_height_label_with_only_whitespace_gets_zero_height():
    label = Gtk.Label(label='   ')

    compute_optimal_height(label, 150)

    # GTK's own size_request getter floors a requested height of 0 to
    # 1 - the real assertion is "requested 0", not "reports back 0".
    width, height = label.get_size_request()
    assert width == 150
    assert height <= 1


# do_set_property() / do_get_property() #

def test_property_roundtrip_via_the_gobject_property_interface():
    renderer = StoreCellRenderer(None)

    renderer.set_property('editable', True)

    assert renderer.get_property('editable') is True


# _get_pango_layout() #

def test_get_pango_layout_sets_the_wrapped_markup_text():
    renderer = StoreCellRenderer(None)
    textview = Gtk.TextView()

    layout = renderer._get_pango_layout(textview, 'hello <world>', 200, rendering.get_source_font_description())

    assert 'hello' in layout.get_text()


def test_get_pango_layout_defaults_a_falsy_text_to_empty():
    renderer = StoreCellRenderer(None)
    textview = Gtk.TextView()

    layout = renderer._get_pango_layout(textview, None, 200, rendering.get_source_font_description())

    assert layout.get_text() == ''


# compute_cell_height() #

def _renderer_for_unit(source, target):
    renderer = StoreCellRenderer(SimpleNamespace(
        controller=SimpleNamespace(main_controller=SimpleNamespace(
            lang_controller=SimpleNamespace(
                source_lang=SimpleNamespace(code='en'),
                target_lang=SimpleNamespace(code='en'),
            )
        ))
    ))
    renderer.unit = SimpleNamespace(isfuzzy=lambda: False, source=source, target=target)
    return renderer


def test_compute_cell_height_uses_the_taller_of_source_and_target():
    renderer = _renderer_for_unit('short', 'a much, much longer translated string than the source')
    textview = Gtk.TextView()

    height = renderer.compute_cell_height(textview, 200)

    assert height > renderer.ROW_PADDING
    _w, target_h = renderer.target_layout.get_pixel_size()
    assert height == target_h + renderer.ROW_PADDING


def test_compute_cell_height_right_aligns_for_rtl():
    renderer = _renderer_for_unit('source', 'target')
    textview = Gtk.TextView()
    textview.set_direction(Gtk.TextDirection.RTL)

    renderer.compute_cell_height(textview, 200)

    assert renderer.source_layout.get_alignment() == 2  # Pango.Alignment.RIGHT
    assert renderer.target_layout.get_alignment() == 2
    textview.set_direction(Gtk.TextDirection.NONE)


# check_editor_height() #

def _sized_textbox(height, visible=True):
    # Realized (via a real OffscreenWindow, like _realized_textview()
    # above) so the parent box's own .size_request() actually reflects
    # the child's requested height - an unrealized box's requisition
    # stays at its default (0), never recomputed from children at all.
    win = Gtk.OffscreenWindow()
    box = Gtk.Box()
    label = Gtk.Label()
    label.set_size_request(-1, height)
    box.add(label)
    win.add(box)
    win.show()
    box.show()
    if visible:
        label.show()
    # Keep the parent window/box alive for as long as the label is -
    # once their only Python reference (these locals) goes out of
    # scope, the child's own .props.visible silently resets to False,
    # a real PyGObject pitfall (the C-level parent/child link alone
    # isn't enough to keep the Python wrapper's property state intact).
    label._test_parent_refs = (win, box)
    return label


def test_check_editor_height_shrinks_a_too_tall_textbox():
    renderer = StoreCellRenderer(None)
    tall_target = _sized_textbox(500)
    editor = SimpleNamespace(_widgets={
        'notes': {},
        'sources': [],
        'targets': [tall_target],
    })

    renderer.check_editor_height(editor, width=200, parentheight=100)

    assert tall_target.get_parent().get_size_request()[1] == 100


def test_check_editor_height_skips_an_invisible_textbox():
    renderer = StoreCellRenderer(None)
    hidden_target = _sized_textbox(500, visible=False)
    visible_source = _sized_textbox(500)
    editor = SimpleNamespace(_widgets={
        'notes': {},
        'sources': [visible_source],
        'targets': [hidden_target],
    })

    renderer.check_editor_height(editor, width=200, parentheight=100)

    # The invisible one is left alone - only the visible source got
    # resized (there's only one visible textbox, so it alone absorbs
    # the full max_tb_height, same as the "shrinks" test above).
    assert hidden_target.get_parent().get_size_request() == (-1, -1)
    assert visible_source.get_parent().get_size_request()[1] == 100


def test_check_editor_height_gives_up_when_notes_leave_no_room():
    renderer = StoreCellRenderer(None)
    tall_target = _sized_textbox(500)
    # check_editor_height() calls .size_request() on the note directly
    # (not via a parent) - it needs to be realized itself, same as
    # _sized_textbox()'s own targets/sources, or its explicit request
    # never shows up in the *computed* size .size_request() reports.
    huge_note = _sized_textbox(1000)
    editor = SimpleNamespace(_widgets={
        'notes': {'note1': huge_note},
        'sources': [],
        'targets': [tall_target],
    })

    renderer.check_editor_height(editor, width=200, parentheight=100)  # must not raise

    # No textbox was ever resized - the explicit (not natural) size
    # request stays at its GTK default.
    assert tall_target.get_parent().get_size_request() == (-1, -1)


# do_get_size() - the non-editable branch and the resize-debounce cache #

def _renderer_with_view(is_resizing=False):
    treeview = SimpleNamespace(is_resizing=is_resizing)
    view = SimpleNamespace(
        _treeview=treeview,
        controller=SimpleNamespace(main_controller=SimpleNamespace(
            lang_controller=SimpleNamespace(
                source_lang=SimpleNamespace(code='en'),
                target_lang=SimpleNamespace(code='en'),
            )
        )),
    )
    renderer = StoreCellRenderer(view)
    renderer.unit = SimpleNamespace(isfuzzy=lambda: False, source='src', target='tgt')
    return renderer


def _toplevel_widget():
    win = Gtk.OffscreenWindow()
    win.set_default_size(400, 300)
    box = Gtk.Box()
    win.add(box)
    win.show_all()
    return box


def test_do_get_size_computes_and_caches_height_when_not_resizing():
    renderer = _renderer_with_view(is_resizing=False)
    renderer.editable = False
    widget = _toplevel_widget()

    _x, _y, _width, height = renderer.do_get_size(widget, None)

    assert height > 0
    assert renderer._cached_height == height


def test_do_get_size_reuses_the_cached_height_while_resizing():
    renderer = _renderer_with_view(is_resizing=True)
    renderer.editable = False
    renderer._cached_height = 12345
    widget = _toplevel_widget()

    _x, _y, _width, height = renderer.do_get_size(widget, None)

    assert height == 12345


def test_set_unit_clears_the_cached_height():
    renderer = StoreCellRenderer(None)
    renderer._cached_height = 999

    renderer.unit = SimpleNamespace(isfuzzy=lambda: False)

    assert renderer._cached_height is None


def test_set_unit_marks_the_cell_background_for_a_fuzzy_unit():
    renderer = StoreCellRenderer(None)

    renderer.unit = SimpleNamespace(isfuzzy=lambda: True)

    assert renderer.props.cell_background_set is True


def test_set_unit_clears_the_cell_background_for_a_non_fuzzy_unit():
    renderer = StoreCellRenderer(None)
    renderer.unit = SimpleNamespace(isfuzzy=lambda: True)

    renderer.unit = SimpleNamespace(isfuzzy=lambda: False)

    assert renderer.props.cell_background_set is False


# do_render() #

def test_do_render_paints_nothing_and_returns_true_when_editable():
    renderer = StoreCellRenderer(None)
    renderer.editable = True

    assert renderer.do_render(None, None, None, None, Gtk.CellRendererState(0)) is True


def test_do_render_paints_the_source_and_target_layouts(monkeypatch):
    # Real pixel-level verification (render to a surface, check
    # non-zero data) hit a genuine Windows-only Cairo failure
    # (cairo.MemoryError on surface.flush(), confirmed via CI - not
    # reproducible on macOS/Linux) in this already-deprecated
    # Gtk.paint_layout() path. Verifying the calls themselves is both
    # more portable and a more direct test of do_render()'s own logic
    # (source/target offsets, which layout goes where) anyway.
    paints = []
    monkeypatch.setattr(Gtk, 'paint_layout', lambda **kwargs: paints.append(kwargs))
    renderer = _renderer_with_view()
    renderer.editable = False
    widget = _toplevel_widget()

    renderer.do_render(object(), widget, _rectangle(200, 50), _rectangle(200, 50), Gtk.CellRendererState(0))

    assert len(paints) == 2
    assert paints[0]['layout'] is renderer.source_layout
    assert paints[1]['layout'] is renderer.target_layout
    assert paints[1]['x'] > paints[0]['x']  # target sits right of source (LTR)


# _on_editor_done() / _on_modified() #

def test_on_editor_done_emits_editing_done_with_the_editors_state():
    renderer = StoreCellRenderer(None)
    editor = SimpleNamespace(get_path=lambda: '/tmp/f.po:1', must_advance=True, is_modified=lambda: False)
    emitted = []
    renderer.connect('editing-done', lambda r, path, advance, modified: emitted.append((path, advance, modified)))

    result = renderer._on_editor_done(editor)

    assert result is True
    assert emitted == [('/tmp/f.po:1', True, False)]


def test_on_modified_emits_modified():
    renderer = StoreCellRenderer(None)
    emitted = []
    renderer.connect('modified', lambda r: emitted.append(True))

    renderer._on_modified(None)

    assert emitted == [True]
