#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk, Pango

from virtaal.plugins.terminology.models.localfile import localfileview
from virtaal.plugins.terminology.models.localfile.localfileview import (
    FileSelectDialog,
    LocalFileView,
    TermAddDialog,
)
from virtaal.views.widgets.wordatcursor import WordAtCursorSelector


def _fake_view_with_selection(text=None):
    view = LocalFileView.__new__(LocalFileView)
    view._word_selector = WordAtCursorSelector()
    calls = []
    view._on_add_term = lambda *args: calls.append(args)
    textbox = SimpleNamespace(buffer=Gtk.TextBuffer())
    if text is not None:
        textbox.buffer.set_text(text)
        textbox.buffer.select_range(
            textbox.buffer.get_start_iter(), textbox.buffer.get_end_iter())
    return view, textbox, calls


class _FakeEntry:
    def grab_focus(self):
        pass


class _FakeTopWindow:
    def __init__(self):
        self.presented = False

    def present(self):
        self.presented = True


class _FakeDialog:
    def __init__(self, transient_for=None):
        self.calls = []
        self._transient_for = transient_for

    def set_transient_for(self, window):
        pass

    def get_transient_for(self):
        return self._transient_for

    def show(self):
        self.calls.append('show')

    def present(self):
        self.calls.append('present')

    def run(self):
        return Gtk.ResponseType.CANCEL

    def hide(self):
        pass


def test_run_shows_before_presenting():
    # present() only raises/focuses an already-realized window - on the
    # very first run() it isn't yet, so show() has to come first or the
    # dialog opens without real OS-level keyboard focus on macOS.
    add_dialog = TermAddDialog.__new__(TermAddDialog)
    add_dialog.dialog = _FakeDialog()
    add_dialog.ent_source = _FakeEntry()
    add_dialog.reset = lambda: None
    add_dialog._on_entry_changed = lambda *args: None

    add_dialog.run()

    assert add_dialog.dialog.calls == ['show', 'present']


def test_run_restores_the_parents_focus_on_close(monkeypatch):
    from virtaal.plugins.terminology.models.localfile import localfileview
    monkeypatch.setattr(localfileview.GLib, 'idle_add', lambda func, *args: func(*args))

    add_dialog = TermAddDialog.__new__(TermAddDialog)
    top_window = _FakeTopWindow()
    add_dialog.dialog = _FakeDialog(transient_for=top_window)
    add_dialog.ent_source = _FakeEntry()
    add_dialog.reset = lambda: None
    add_dialog._on_entry_changed = lambda *args: None

    add_dialog.run()

    assert top_window.presented


def test_populate_popup_does_nothing_without_a_selection():
    view, textbox, calls = _fake_view_with_selection()
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    assert menu.get_children() == []


def test_populate_popup_uses_the_word_under_the_cursor_when_nothing_is_selected():
    # A plain right-click (nothing dragged out first) shouldn't
    # require selecting a word first - same as the Look-up plugin.
    view = LocalFileView.__new__(LocalFileView)
    view._word_selector = WordAtCursorSelector()
    calls = []
    view._on_add_term = lambda *args: calls.append(args)
    textbox = SimpleNamespace(buffer=Gtk.TextBuffer())
    textbox.buffer.set_text('a widget here')
    textbox.buffer.place_cursor(textbox.buffer.get_iter_at_offset(4))  # inside "widget"
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    items = menu.get_children()
    assert items[1].get_label() == 'Add Term "widget"...'


def test_populate_popup_adds_add_term_for_a_selection():
    view, textbox, calls = _fake_view_with_selection('widget')
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    items = menu.get_children()
    assert len(items) == 2
    assert isinstance(items[0], Gtk.SeparatorMenuItem)
    assert items[1].get_label() == 'Add Term "widget"...'

    items[1].activate()
    assert calls


def test_populate_popup_ellipsizes_a_long_selection():
    view, textbox, calls = _fake_view_with_selection('a' * 60)
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    item = menu.get_children()[1]
    assert item.get_label() == 'Add Term "%s"...' % ('a' * 60)
    label_widget = item.get_child()
    assert label_widget.get_ellipsize() == Pango.EllipsizeMode.MIDDLE
    assert label_widget.get_max_width_chars() == 40


def test_treeview_scrolled_window_is_not_focusable(monkeypatch):
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the treeview inside it (same issue as prefsview.py's
    # plugin/placeables lists and weblookup.py's URL list).
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)

    dialog = FileSelectDialog(model=SimpleNamespace(controller=None, config={'files': []}))

    assert not dialog.tvw_termfiles.get_parent().get_can_focus()


class _FakeAddChooser:
    def __init__(self, response, filenames=()):
        self._response = response
        self._filenames = filenames

    def run(self):
        return self._response

    def hide(self):
        pass

    def get_filenames(self):
        return self._filenames


def test_add_file_clicked_adds_the_file_on_accept(monkeypatch, tmp_path):
    # GtkFileChooserNative returns ACCEPT on a real accept, never OK -
    # comparing against OK meant a real pick silently did nothing.
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    picked = tmp_path / 'terms.po'
    picked.write_text('')
    config = {'files': []}
    fake_controller = SimpleNamespace(main_controller=SimpleNamespace(view=None))
    model = SimpleNamespace(
        controller=fake_controller, config=config,
        save_config=lambda: None, load_files=lambda: None)
    dialog = FileSelectDialog(model=model)
    dialog.add_chooser = _FakeAddChooser(Gtk.ResponseType.ACCEPT, filenames=[str(picked)])

    dialog._on_add_file_clicked(None)

    assert str(picked) in config['files']


def test_add_file_clicked_restores_the_parents_focus_regardless_of_response(monkeypatch):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    calls = []
    monkeypatch.setattr(localfileview.GLib, 'idle_add', lambda func, *args: calls.append((func, args)))
    dialog = FileSelectDialog(model=SimpleNamespace(controller=None, config={'files': []}))
    dialog.add_chooser = _FakeAddChooser(Gtk.ResponseType.CANCEL)

    dialog._on_add_file_clicked(None)

    assert len(calls) == 1
