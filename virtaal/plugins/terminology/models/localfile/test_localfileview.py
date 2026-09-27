#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
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


def test_run_sets_the_transient_parent_when_given_a_real_widget():
    add_dialog = TermAddDialog.__new__(TermAddDialog)
    add_dialog.dialog = _FakeDialog()
    calls = []
    add_dialog.dialog.set_transient_for = calls.append
    add_dialog.ent_source = _FakeEntry()
    add_dialog.reset = lambda: None
    add_dialog._on_entry_changed = lambda *args: None
    window = Gtk.Window()

    add_dialog.run(parent=window)

    assert calls == [window]


def test_run_adds_the_term_when_the_dialog_is_accepted():
    add_dialog = TermAddDialog.__new__(TermAddDialog)
    dialog = _FakeDialog()
    dialog.run = lambda: Gtk.ResponseType.OK
    add_dialog.dialog = dialog
    add_dialog.ent_source = SimpleNamespace(get_text=lambda: 'cat', grab_focus=lambda: None)
    add_dialog.ent_target = SimpleNamespace(get_text=lambda: 'kat')
    add_dialog.reset = lambda: None
    add_dialog._on_entry_changed = lambda *args: None
    added = []
    add_dialog.add_term_unit = lambda source, target: added.append((source, target))

    add_dialog.run()

    assert added == [('cat', 'kat')]


def test_init_wires_entry_changed_signals_to_on_entry_changed(monkeypatch):
    # Real Gtk.Builder construction (like FileSelectDialog's own
    # construction tests) - __init__/_get_widgets() themselves are
    # otherwise pure widget-wiring boilerplate not worth faking.
    calls = []
    monkeypatch.setattr(TermAddDialog, '_on_entry_changed', lambda self, entry: calls.append(entry))
    model = SimpleNamespace(controller=SimpleNamespace(main_controller=SimpleNamespace(
        lang_controller=None, unit_controller=None)))

    dialog = TermAddDialog(model=model)

    assert dialog.cmb_termfile.get_model() is dialog.lst_termfiles

    dialog.ent_source.emit('changed')
    dialog.ent_target.emit('changed')

    assert len(calls) == 2


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
    assert items[1].get_label() == 'Add Term "widget"…'


def test_populate_popup_adds_add_term_for_a_selection():
    view, textbox, calls = _fake_view_with_selection('widget')
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    items = menu.get_children()
    assert len(items) == 2
    assert isinstance(items[0], Gtk.SeparatorMenuItem)
    assert items[1].get_label() == 'Add Term "widget"…'

    items[1].activate()
    assert calls


def test_populate_popup_ellipsizes_a_long_selection():
    view, textbox, calls = _fake_view_with_selection('a' * 60)
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    item = menu.get_children()[1]
    assert item.get_label() == 'Add Term "%s"…' % ('a' * 60)
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


def test_add_file_clicked_shows_an_error_for_a_file_that_no_longer_exists(monkeypatch):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    config = {'files': []}
    errors = []
    fake_controller = SimpleNamespace(main_controller=SimpleNamespace(
        view=SimpleNamespace(show_error_dialog=lambda title, message: errors.append((title, message)))))
    model = SimpleNamespace(
        controller=fake_controller, config=config,
        save_config=lambda: None, load_files=lambda: None)
    dialog = FileSelectDialog(model=model)
    dialog.add_chooser = _FakeAddChooser(Gtk.ResponseType.ACCEPT, filenames=['/no/such/file.po'])

    dialog._on_add_file_clicked(None)

    assert config['files'] == []
    assert len(errors) == 1
    assert 'not a usable file' in errors[0][1]


def test_add_file_clicked_skips_a_filename_already_in_the_list(monkeypatch, tmp_path):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    picked = tmp_path / 'terms.po'
    picked.write_text('')
    config = {'files': [str(picked)]}
    model = SimpleNamespace(
        controller=SimpleNamespace(main_controller=SimpleNamespace(view=None)), config=config,
        save_config=lambda: None, load_files=lambda: None)
    dialog = FileSelectDialog(model=model)
    dialog.add_chooser = _FakeAddChooser(Gtk.ResponseType.ACCEPT, filenames=[str(picked)])

    dialog._on_add_file_clicked(None)

    assert config['files'] == [str(picked)]  # not duplicated


def test_add_file_clicked_restores_the_parents_focus_regardless_of_response(monkeypatch):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    calls = []
    monkeypatch.setattr(localfileview.GLib, 'idle_add', lambda func, *args: calls.append((func, args)))
    dialog = FileSelectDialog(model=SimpleNamespace(controller=None, config={'files': []}))
    dialog.add_chooser = _FakeAddChooser(Gtk.ResponseType.CANCEL)

    dialog._on_add_file_clicked(None)

    assert len(calls) == 1


# LocalFileView.destroy() #

def test_destroy_disconnects_signals_and_removes_menu_items():
    view = LocalFileView.__new__(LocalFileView)
    disconnected = []
    view._signal_tracker = SimpleNamespace(disconnect_all=lambda: disconnected.append(True))
    removed = []
    view.menu = SimpleNamespace(remove=removed.append)
    view.mnu_select_files = 'select-files-item'
    view.mnu_add_term = 'add-term-item'

    view.destroy()

    assert disconnected == [True]
    assert removed == ['select-files-item', 'add-term-item']


# LocalFileView.addterm / .fileselect properties #

def test_addterm_property_lazily_constructs_and_caches(monkeypatch):
    created = []

    class _FakeAddDialog:
        def __init__(self, model):
            created.append(model)
    monkeypatch.setattr(localfileview, 'TermAddDialog', _FakeAddDialog)
    view = LocalFileView.__new__(LocalFileView)
    view.term_model = 'model'
    view._addterm = None

    first = view.addterm
    second = view.addterm

    assert isinstance(first, _FakeAddDialog)
    assert first is second
    assert created == ['model']


def test_fileselect_property_lazily_constructs_and_caches(monkeypatch):
    created = []

    class _FakeFileSelect:
        def __init__(self, model):
            created.append(model)
    monkeypatch.setattr(localfileview, 'FileSelectDialog', _FakeFileSelect)
    view = LocalFileView.__new__(LocalFileView)
    view.term_model = 'model'
    view._fileselect = None

    first = view.fileselect
    second = view.fileselect

    assert isinstance(first, _FakeFileSelect)
    assert first is second
    assert created == ['model']


# LocalFileView's trivial event-handler delegators #

def test_on_add_term_runs_the_addterm_dialog():
    view = LocalFileView.__new__(LocalFileView)
    calls = []
    view._addterm = SimpleNamespace(run=lambda parent: calls.append(parent))
    view.mainview = SimpleNamespace(main_window='main-window')

    view._on_add_term()

    assert calls == ['main-window']


def test_on_select_term_files_runs_the_fileselect_dialog():
    view = LocalFileView.__new__(LocalFileView)
    calls = []
    view._fileselect = SimpleNamespace(run=lambda parent: calls.append(parent))
    view.mainview = SimpleNamespace(main_window='main-window')

    view._on_select_term_files(None)

    assert calls == ['main-window']


def test_populate_popup_does_nothing_for_a_whitespace_only_selection():
    # buf.get_text().strip() can turn a real, non-empty GTK selection
    # into an empty string - a second, later guard from the one
    # covered by test_populate_popup_does_nothing_without_a_selection.
    view, textbox, calls = _fake_view_with_selection('   ')
    menu = Gtk.Menu()

    view._on_populate_popup(textbox, menu)

    assert menu.get_children() == []


# FileSelectDialog._init_treeview()'s extend-file selection logic #

def test_init_treeview_lists_configured_files_and_marks_the_extend_file(monkeypatch):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    model = SimpleNamespace(controller=None, config={'files': ['a.po', 'b.po'], 'extendfile': 'b.po'})

    dialog = FileSelectDialog(model=model)

    assert [(row[0], row[1]) for row in dialog.lst_files] == [('a.po', False), ('b.po', True)]


def test_init_treeview_defaults_to_the_first_file_when_none_is_marked_to_extend(monkeypatch):
    monkeypatch.setattr(FileSelectDialog, '_init_add_chooser', lambda self: None)
    saved = []
    model = SimpleNamespace(
        controller=None,
        config={'files': ['a.po', 'b.po'], 'extendfile': ''},
        save_config=lambda: saved.append(True),
    )

    dialog = FileSelectDialog(model=model)

    assert [(row[0], row[1]) for row in dialog.lst_files] == [('a.po', True), ('b.po', False)]
    assert model.config['extendfile'] == 'a.po'
    assert saved == [True]


# FileSelectDialog.clear_selection() / run() #

def test_clear_selection_unselects_all_rows():
    dialog = FileSelectDialog.__new__(FileSelectDialog)
    unselected = []
    dialog.tvw_termfiles = SimpleNamespace(
        get_selection=lambda: SimpleNamespace(unselect_all=lambda: unselected.append(True)))

    dialog.clear_selection()

    assert unselected == [True]


class _FakeFileSelectGtkDialog:
    def __init__(self, transient_for=None):
        self.calls = []
        self._transient_for = transient_for

    def set_transient_for(self, window):
        self.calls.append(('set_transient_for', window))

    def get_transient_for(self):
        return self._transient_for

    def show_all(self):
        self.calls.append('show_all')

    def present(self):
        self.calls.append('present')

    def run(self):
        self.calls.append('run')
        return Gtk.ResponseType.CANCEL

    def hide(self):
        self.calls.append('hide')


def test_run_shows_the_dialog_and_clears_selection():
    dialog = FileSelectDialog.__new__(FileSelectDialog)
    dialog.dialog = _FakeFileSelectGtkDialog()
    cleared = []
    dialog.clear_selection = lambda: cleared.append(True)

    dialog.run()

    assert cleared == [True]
    assert dialog.dialog.calls == ['show_all', 'present', 'run', 'hide']


def test_file_select_dialog_run_sets_the_transient_parent_when_given_a_real_widget():
    dialog = FileSelectDialog.__new__(FileSelectDialog)
    dialog.dialog = _FakeFileSelectGtkDialog()
    dialog.clear_selection = lambda: None
    window = Gtk.Window()

    dialog.run(parent=window)

    assert ('set_transient_for', window) in dialog.dialog.calls


def test_file_select_dialog_run_restores_the_parents_focus_on_close(monkeypatch):
    idle_calls = []
    monkeypatch.setattr(localfileview.GLib, 'idle_add', lambda func, *args: idle_calls.append((func, args)))
    top_window = _FakeTopWindow()
    dialog = FileSelectDialog.__new__(FileSelectDialog)
    dialog.dialog = _FakeFileSelectGtkDialog(transient_for=top_window)
    dialog.clear_selection = lambda: None

    dialog.run()

    assert idle_calls == [(top_window.present, ())]


# FileSelectDialog's remaining event handlers - real Gtk.ListStore/TreeView #

def _dialog_with_files(files, extendfile=''):
    dialog = FileSelectDialog.__new__(FileSelectDialog)
    dialog.lst_files = Gtk.ListStore(str, bool)
    for f in files:
        dialog.lst_files.append([f, f == extendfile])
    dialog.tvw_termfiles = Gtk.TreeView(model=dialog.lst_files)
    dialog.btn_open_termfile = Gtk.Button()
    dialog.btn_remove_file = Gtk.Button()
    return dialog


def test_on_remove_file_clicked_does_nothing_without_a_selection():
    dialog = _dialog_with_files(['a.po'])
    dialog.term_model = SimpleNamespace(config={'files': ['a.po']})

    dialog._on_remove_file_clicked(None)

    assert dialog.term_model.config['files'] == ['a.po']


def test_on_remove_file_clicked_removes_the_selected_non_extend_file():
    dialog = _dialog_with_files(['a.po', 'b.po'], extendfile='a.po')
    saved = []
    dialog.term_model = SimpleNamespace(
        config={'files': ['a.po', 'b.po'], 'extendfile': 'a.po'},
        save_config=lambda: saved.append(True),
        load_files=lambda: None,
    )
    dialog.tvw_termfiles.get_selection().select_path(Gtk.TreePath(1))  # b.po

    dialog._on_remove_file_clicked(None)

    assert dialog.term_model.config['files'] == ['a.po']
    assert saved == [True]
    assert [row[0] for row in dialog.lst_files] == ['a.po']


def test_on_remove_file_clicked_picks_a_new_extend_file_when_removing_the_current_one():
    dialog = _dialog_with_files(['a.po', 'b.po'], extendfile='a.po')
    dialog.term_model = SimpleNamespace(
        config={'files': ['a.po', 'b.po'], 'extendfile': 'a.po'},
        save_config=lambda: None,
        load_files=lambda: None,
    )
    dialog.tvw_termfiles.get_selection().select_path(Gtk.TreePath(0))  # a.po, the extend file

    dialog._on_remove_file_clicked(None)

    assert dialog.term_model.config['extendfile'] == 'b.po'
    assert [(row[0], row[1]) for row in dialog.lst_files] == [('b.po', True)]


def test_on_open_termfile_clicked_does_nothing_without_a_selection():
    dialog = _dialog_with_files(['a.po'])
    dialog.term_model = SimpleNamespace(controller=SimpleNamespace(main_controller=SimpleNamespace(
        open_file=lambda f: pytest.fail('must not open without a selection'))))

    dialog._on_open_termfile_clicked(None)


def test_on_open_termfile_clicked_opens_the_selected_file():
    dialog = _dialog_with_files(['a.po', 'b.po'])
    opened = []
    dialog.term_model = SimpleNamespace(controller=SimpleNamespace(
        main_controller=SimpleNamespace(open_file=opened.append)))
    dialog.tvw_termfiles.get_selection().select_path(Gtk.TreePath(1))

    dialog._on_open_termfile_clicked(None)

    assert opened == ['b.po']


def test_on_selection_changed_disables_buttons_without_a_selection():
    dialog = _dialog_with_files(['a.po'])

    dialog._on_selection_changed(dialog.tvw_termfiles.get_selection())

    assert dialog.btn_open_termfile.get_sensitive() is False
    assert dialog.btn_remove_file.get_sensitive() is False


def test_on_selection_changed_enables_buttons_with_a_selection():
    dialog = _dialog_with_files(['a.po'])
    dialog.tvw_termfiles.get_selection().select_path(Gtk.TreePath(0))

    dialog._on_selection_changed(dialog.tvw_termfiles.get_selection())

    assert dialog.btn_open_termfile.get_sensitive() is True
    assert dialog.btn_remove_file.get_sensitive() is True


def test_on_toggle_marks_only_the_toggled_row_as_the_extend_file():
    dialog = _dialog_with_files(['a.po', 'b.po'], extendfile='a.po')
    saved = []
    dialog.term_model = SimpleNamespace(config={'extendfile': 'a.po'}, save_config=lambda: saved.append(True))

    dialog._on_toggle(None, '1')  # toggle b.po

    assert [(row[0], row[1]) for row in dialog.lst_files] == [('a.po', False), ('b.po', True)]
    assert dialog.term_model.config['extendfile'] == 'b.po'
    assert saved == [True]


# TermAddDialog.add_term_unit() #

class _FakeTermUnit:
    def __init__(self, source):
        self.source = source
        self.target = None
        self.notes = []

    def addnote(self, note):
        self.notes.append(note)


class _FakeTermStore:
    def __init__(self):
        self.units = []
        self.saved = False

    def addsourceunit(self, source):
        unit = _FakeTermUnit(source)
        self.units.append(unit)
        return unit

    def save(self):
        self.saved = True


def _add_term_dialog(comment_text=''):
    dialog = TermAddDialog.__new__(TermAddDialog)
    dialog.cmb_termfile = SimpleNamespace(get_active_text=lambda: 'terms.po')
    buff = Gtk.TextBuffer()
    buff.set_text(comment_text)
    dialog.txt_comment = SimpleNamespace(get_buffer=lambda: buff)
    return dialog


def test_add_term_unit_does_nothing_without_a_target_store():
    dialog = _add_term_dialog()
    dialog.term_model = SimpleNamespace(get_store_for_filename=lambda f: None)

    dialog.add_term_unit('cat', 'kat')  # must not raise


def test_add_term_unit_adds_a_unit_with_a_comment_and_saves():
    dialog = _add_term_dialog('a helpful comment')
    store = _FakeTermStore()
    extended = []
    rescanned = []
    dialog.term_model = SimpleNamespace(
        get_store_for_filename=lambda f: store,
        matcher=SimpleNamespace(extendtm=extended.append),
        controller=SimpleNamespace(rescan_current_unit=lambda: rescanned.append(True)),
    )

    dialog.add_term_unit('cat', 'kat')

    unit = store.units[0]
    assert (unit.source, unit.target, unit.notes) == ('cat', 'kat', ['a helpful comment'])
    assert store.saved is True
    assert extended == [unit]
    assert rescanned == [True]


def test_add_term_unit_skips_the_note_when_the_comment_is_empty():
    dialog = _add_term_dialog('')
    store = _FakeTermStore()
    dialog.term_model = SimpleNamespace(
        get_store_for_filename=lambda f: store,
        matcher=SimpleNamespace(extendtm=lambda u: None),
        controller=SimpleNamespace(rescan_current_unit=lambda: None),
    )

    dialog.add_term_unit('cat', 'kat')

    assert store.units[0].notes == []


# TermAddDialog._on_entry_changed() #

def _entry_changed_dialog(duplicates=None, same_src_units=None):
    dialog = TermAddDialog.__new__(TermAddDialog)
    dialog.btn_add_term = Gtk.Button()
    dialog.eb_add_term_errors = Gtk.EventBox()
    dialog.lbl_add_term_errors = Gtk.Label()
    dialog.ent_source = SimpleNamespace(get_text=lambda: 'cat')
    dialog.ent_target = SimpleNamespace(get_text=lambda: 'kat')
    dialog.term_model = SimpleNamespace(
        get_duplicates=lambda src, tgt: duplicates or [],
        get_units_with_source=lambda src: same_src_units or [],
    )
    return dialog


def test_on_entry_changed_flags_an_identical_existing_entry():
    dialog = _entry_changed_dialog(duplicates=[object()])

    dialog._on_entry_changed(None)

    assert dialog.btn_add_term.get_sensitive() is False
    assert dialog.eb_add_term_errors.get_visible() is True
    assert dialog.lbl_add_term_errors.get_text() == 'Identical entry already exists.'


def test_on_entry_changed_warns_about_an_existing_translation_for_the_same_source():
    existing = SimpleNamespace(target='kitty')
    dialog = _entry_changed_dialog(same_src_units=[existing])

    dialog._on_entry_changed(None)

    assert dialog.eb_add_term_errors.get_visible() is True
    assert 'kitty' in dialog.lbl_add_term_errors.get_text()


def test_on_entry_changed_clears_errors_and_enables_add_when_clean():
    dialog = _entry_changed_dialog()
    dialog.btn_add_term.set_sensitive(False)
    dialog.eb_add_term_errors.show_all()

    dialog._on_entry_changed(None)

    assert dialog.btn_add_term.get_sensitive() is True
    assert dialog.eb_add_term_errors.get_visible() is False
