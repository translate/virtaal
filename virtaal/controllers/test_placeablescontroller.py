#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.views import placeablesguiinfo


class _FakeTextbox:
    def __init__(self, calls, name, visible=True, parent_visible=True):
        self.props = SimpleNamespace(visible=visible)
        self._parent_visible = parent_visible
        self._calls = calls
        self.name = name

    def is_visible(self):
        return self.props.visible and self._parent_visible

    def refresh(self):
        self._calls.append(('refresh', self.name))


def _controller(sources=(), targets=()):
    controller = PlaceablesController.__new__(PlaceablesController)
    unitview = SimpleNamespace(
        sources=list(sources), targets=list(targets),
        disable_signals=lambda names: None, enable_signals=lambda names: None,
    )
    controller.main_controller = SimpleNamespace(unit_controller=SimpleNamespace(view=unitview))
    return controller


def _record_update_style(monkeypatch, calls):
    monkeypatch.setattr(placeablesguiinfo, 'update_style',
                        lambda widget: calls.append(('update_style', widget)))


def test_style_set_with_no_file_open_still_updates_the_placeable_colours(monkeypatch):
    # #3964: a dark theme applied at startup, before any text box exists,
    # left the light defaults in place.
    calls = []
    _record_update_style(monkeypatch, calls)

    _controller()._on_style_set(None)

    assert len(calls) == 1
    assert isinstance(calls[0][1], Gtk.TextView)


def test_style_set_updates_the_colours_before_redrawing_the_text(monkeypatch):
    calls = []
    _record_update_style(monkeypatch, calls)
    source = _FakeTextbox(calls, 'source')
    target = _FakeTextbox(calls, 'target')

    _controller(sources=[source], targets=[target])._on_style_set(None)

    assert calls == [('update_style', source), ('refresh', 'source'), ('refresh', 'target')]


def test_style_set_ignores_hidden_text_boxes(monkeypatch):
    calls = []
    _record_update_style(monkeypatch, calls)
    hidden = _FakeTextbox(calls, 'hidden', visible=False)
    target = _FakeTextbox(calls, 'target')

    _controller(sources=[hidden], targets=[target])._on_style_set(None)

    assert calls == [('update_style', target), ('refresh', 'target')]



def test_style_set_ignores_text_boxes_in_a_hidden_container(monkeypatch):
    # Unused plural targets: UnitView hides their container, and they still
    # hold the last plural unit's text, so refreshing one edits the unit.
    calls = []
    _record_update_style(monkeypatch, calls)
    target = _FakeTextbox(calls, 'target')
    unused_plural = _FakeTextbox(calls, 'unused plural', parent_visible=False)

    _controller(targets=[target, unused_plural])._on_style_set(None)

    assert calls == [('update_style', target), ('refresh', 'target')]
