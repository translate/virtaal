#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.plugins.tm.tmwidgets import TMSourceColRenderer, TMWindow


class _FakeCellRenderer:
    def __init__(self):
        self.properties = {}

    def set_property(self, name, value):
        self.properties[name] = value


def _percent(match_data):
    tree_model = type('M', (), {'get_value': staticmethod(lambda iter, col: match_data)})()
    cell_renderer = _FakeCellRenderer()
    TMWindow._percent_data_func(None, None, cell_renderer, tree_model, None, None)
    return cell_renderer.properties


def test_percent_data_func_shows_the_exact_quality_within_range():
    properties = _percent({'quality': 75, 'source': 'a', 'target': 'b'})
    assert properties['value'] == 75
    assert properties['text'] == '75%'


def test_percent_data_func_shows_a_question_mark_for_a_match_with_no_quality():
    properties = _percent({'source': 'a', 'target': 'b'})
    assert properties['value'] == 0
    assert properties['text'] == '?'


# TMSourceColRenderer: no-op when the match has no tmsource to show
# (e.g. a plain MT suggestion).

def test_do_get_size_returns_zero_without_a_tm_source():
    renderer = TMSourceColRenderer(view=None)
    renderer.matchdata = {'source': 'a'}

    assert renderer.do_get_size(widget=None, cell_area=None) == (0, 0, 0, 0)


def test_do_render_does_nothing_without_a_tm_source():
    renderer = TMSourceColRenderer(view=None)
    renderer.matchdata = {'source': 'a'}

    renderer.do_render(window=None, widget=None, _background_area=None, cell_area=None, _flags=None)
