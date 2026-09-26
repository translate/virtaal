#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest

from virtaal.common import GObjectWrapper
from virtaal.controllers.storecontroller import StoreController
from virtaal.support.bundleprojstore import BundleProjectStore


def _fake_bundle(zip_filename):
    """A BundleProjectStore with no real zip file behind it - bypasses
    __init__ (which would create one on disk) via __new__, since these
    tests only need something that isinstance()-checks as the real class."""
    bundle = BundleProjectStore.__new__(BundleProjectStore)
    bundle.zip = SimpleNamespace(filename=zip_filename)
    return bundle


def _fake_storemodel_factory(units):
    """A stand-in for virtaal.models.storemodel.StoreModel, constructed the
    same way open_file() constructs the real one: StoreModel(filename, self)."""

    class _FakeStoreModel:
        def __init__(self, filename, store_controller):
            self.filename = filename
            self.store_controller = store_controller
            self._trans_store = SimpleNamespace(filename=filename)
            self.stats = {'total': list(range(len(units)))}

        def get_units(self):
            return units

    return _FakeStoreModel


def _controller():
    controller = StoreController.__new__(StoreController)
    # A real GObject.Object.__init__() (not just __new__) is needed for
    # connect()/emit() to work - close_file()/update_file() below emit
    # real signals.
    GObjectWrapper.__init__(controller)
    controller.project = None
    controller.store = None
    controller._tempfiles = []
    controller.handler_ids = {}
    return controller


# destroy() #

def test_destroy_with_nothing_open_is_a_noop():
    controller = _controller()
    controller.destroy()  # must not raise


def test_destroy_unlinks_tempfiles_and_swallows_errors(tmp_path):
    controller = _controller()
    real_tempfile = tmp_path / "preview.po"
    real_tempfile.write_text("data")
    controller._tempfiles = [str(real_tempfile), str(tmp_path / "already-gone.po")]

    controller.destroy()  # must not raise despite the second unlink failing

    assert not real_tempfile.exists()


def test_destroy_deletes_the_project():
    controller = _controller()
    deleted = []

    class _Project:
        def __del__(self):
            deleted.append(True)

    controller.project = _Project()

    controller.destroy()

    assert deleted == [True]


# get_nplurals() #

def test_get_nplurals_uses_own_store_by_default():
    controller = _controller()
    controller.store = SimpleNamespace(nplurals=3)

    assert controller.get_nplurals() == 3


def test_get_nplurals_uses_the_given_store_when_passed():
    controller = _controller()
    controller.store = SimpleNamespace(nplurals=3)

    assert controller.get_nplurals(SimpleNamespace(nplurals=5)) == 5


def test_get_nplurals_is_zero_without_a_store():
    controller = _controller()

    assert controller.get_nplurals() == 0


# get_bundle_filename() #

def test_get_bundle_filename_for_a_real_bundle():
    controller = _controller()
    controller.project = SimpleNamespace(store=_fake_bundle("bundle.zip"))

    assert controller.get_bundle_filename() == "bundle.zip"


def test_get_bundle_filename_without_a_project():
    controller = _controller()

    assert controller.get_bundle_filename() is None


# get_store_filename() #

def test_get_store_filename_empty_without_a_store():
    controller = _controller()

    assert controller.get_store_filename() == ''


def test_get_store_filename_uses_the_plain_store_filename():
    controller = _controller()
    controller.store = SimpleNamespace(get_filename=lambda: "/path/to/file.po")

    assert controller.get_store_filename() == "/path/to/file.po"


def test_get_store_filename_for_a_bundle():
    controller = _controller()
    controller.store = SimpleNamespace(get_filename=lambda: "/inner/doc.po")
    controller.project = SimpleNamespace(
        store=_fake_bundle("bundle.zip"),
        get_proj_filename=lambda fname: "/inner/doc.po",
    )

    assert controller.get_store_filename() == "bundle.zip:doc.po"


# get_store_checker()/get_store_stats()/get_store_checks() #

def test_get_store_checker_raises_without_a_store():
    controller = _controller()
    with pytest.raises(ValueError):
        controller.get_store_checker()


def test_get_store_checker_returns_the_store_checker():
    controller = _controller()
    controller.store = SimpleNamespace(get_checker=lambda: "the-checker")

    assert controller.get_store_checker() == "the-checker"


def test_get_store_stats_raises_without_a_store():
    controller = _controller()
    with pytest.raises(ValueError):
        controller.get_store_stats()


def test_get_store_stats_returns_the_store_stats():
    controller = _controller()
    controller.store = SimpleNamespace(stats={'total': 3})

    assert controller.get_store_stats() == {'total': 3}


def test_get_store_checks_raises_without_a_store():
    controller = _controller()
    with pytest.raises(ValueError):
        controller.get_store_checks()


def test_get_store_checks_returns_the_store_checks():
    controller = _controller()
    controller.store = SimpleNamespace(checks={'brackets': []})

    assert controller.get_store_checks() == {'brackets': []}


# get_unit_celleditor() #

def test_get_unit_celleditor_delegates_to_the_unit_controller():
    controller = _controller()
    unit = object()
    controller._unit_controller = SimpleNamespace(load_unit=lambda u: ('cell-editable', u))

    assert controller.get_unit_celleditor(unit) == ('cell-editable', unit)


# is_modified()/set_modified() #

def test_is_modified_reflects_the_flag():
    controller = _controller()
    controller._modified = True

    assert controller.is_modified() is True


def test_set_modified_updates_flag_and_saveable():
    controller = _controller()
    saveable_calls = []
    controller.main_controller = SimpleNamespace(set_saveable=saveable_calls.append)

    controller.set_modified(True)

    assert controller._modified is True
    assert saveable_calls == [True]


# unit_controller property #

def test_unit_controller_setter_connects_without_a_previous_one():
    controller = _controller()
    controller._unit_controller = None
    connected = []
    new_unitcontroller = SimpleNamespace(connect=lambda sig, cb: connected.append((sig, cb)) or 'handler-1')

    controller.unit_controller = new_unitcontroller

    assert controller._unit_controller is new_unitcontroller
    assert connected == [('unit-modified', controller._unit_modified)]
    assert controller.handler_ids['unitview.unit-modified'] == 'handler-1'


def test_unit_controller_setter_disconnects_the_previous_one():
    controller = _controller()
    disconnected = []
    old_unitcontroller = SimpleNamespace(disconnect=disconnected.append)
    controller._unit_controller = old_unitcontroller
    controller.handler_ids['unitview.unit-modified'] = 'old-handler'
    new_unitcontroller = SimpleNamespace(connect=lambda sig, cb: 'new-handler')

    controller.unit_controller = new_unitcontroller

    assert disconnected == ['old-handler']
    assert controller._unit_controller is new_unitcontroller
    assert controller.handler_ids['unitview.unit-modified'] == 'new-handler'


# select_unit() #

def test_select_unit_is_a_noop_when_already_selected():
    controller = _controller()
    unit = object()
    controller.cursor = SimpleNamespace(deref=lambda: unit)
    controller.store = None  # would blow up if select_unit tried to use it

    controller.select_unit(unit)  # must not raise


def test_select_unit_sets_the_cursor_index_when_found():
    controller = _controller()
    unit = object()
    other = object()
    controller.cursor = SimpleNamespace(deref=lambda: other, index=None)
    controller.store = SimpleNamespace(get_units=lambda: [other, unit])

    controller.select_unit(unit)

    assert controller.cursor.index == 1


def test_select_unit_forces_the_cursor_index_when_found_and_forced():
    controller = _controller()
    unit = object()
    other = object()
    forced = []
    controller.cursor = SimpleNamespace(deref=lambda: other, force_index=forced.append)
    controller.store = SimpleNamespace(get_units=lambda: [other, unit])

    controller.select_unit(unit, force=True)

    assert forced == [1]


def test_select_unit_defaults_to_index_zero_when_not_found():
    controller = _controller()
    unit = object()
    other = object()
    controller.cursor = SimpleNamespace(deref=lambda: other, index=None)
    controller.store = SimpleNamespace(get_units=lambda: [other])

    controller.select_unit(unit)

    assert controller.cursor.index == 0


# close_file() #

def test_close_file_resets_state_and_emits_store_closed():
    controller = _controller()
    controller.project = object()
    controller.store = object()
    controller._modified = True
    controller.cursor = object()
    saveable_calls = []
    controller.main_controller = SimpleNamespace(set_saveable=saveable_calls.append)
    hidden = []
    controller._view = SimpleNamespace(hide=lambda: hidden.append(True))
    emitted = []
    controller.connect('store-closed', lambda *_: emitted.append(True))

    controller.close_file()

    assert controller.project is None
    assert controller.store is None
    assert controller._modified is False
    assert saveable_calls == [False]
    assert hidden == [True]
    assert controller.cursor is None
    assert emitted == [True]


# open_file() - plain (non-bundle, non-converter-format) path #
# The .zip/converter-format branches aren't covered here: translate-toolkit
# dropped the modules the .zip branch needs entirely (translate/virtaal#3632).

def _open_file_controller(monkeypatch, units):
    monkeypatch.setattr(
        'virtaal.models.storemodel.StoreModel',
        _fake_storemodel_factory(units),
    )
    controller = _controller()
    controller.force_saveas_calls = []
    controller.saveable_calls = []
    controller.main_controller = SimpleNamespace(
        set_force_saveas=controller.force_saveas_calls.append,
        set_saveable=controller.saveable_calls.append,
    )
    controller.shown = []
    controller._view = SimpleNamespace(
        load_store=controller.shown.append,
        show=lambda: controller.shown.append('shown'),
    )
    return controller


def test_open_file_loads_and_shows_a_plain_file(monkeypatch):
    unit = object()
    controller = _open_file_controller(monkeypatch, units=[unit])
    emitted = []
    controller.connect('store-loaded', lambda *_: emitted.append(True))

    controller.open_file('file.po')

    assert controller.store.get_units() == [unit]
    assert controller._modified is False
    assert controller.force_saveas_calls == [False]
    assert controller.saveable_calls == [False]
    assert controller.cursor.model is controller.store
    assert controller.shown == [controller.store, 'shown']
    assert emitted == [True]


def test_open_file_raises_and_cleans_up_for_an_empty_store(monkeypatch):
    controller = _open_file_controller(monkeypatch, units=[])
    hidden = []
    controller._view.hide = lambda: hidden.append(True)

    with pytest.raises(ValueError):
        controller.open_file('empty.po')

    assert controller.store is None  # close_file() cleaned up
    assert hidden == [True]


def test_open_file_forces_saveas_and_renames_a_pot_template(monkeypatch):
    unit = object()
    controller = _open_file_controller(monkeypatch, units=[unit])

    controller.open_file('template.pot')

    assert controller.force_saveas_calls == [True]
    assert controller.store._trans_store.filename == 'template.po'


def test_open_file_strips_the_directory_when_forced_saveas_and_forget_dir(monkeypatch):
    unit = object()
    controller = _open_file_controller(monkeypatch, units=[unit])

    controller.open_file('/some/dir/template.pot', forget_dir=True)

    assert controller.store._trans_store.filename == 'template.po'


# open_file() - bundle (.zip) path #

class _FakeProject:
    """A stand-in for virtaal.support.project.Project - constructed the
    same way _open_bundle() builds the real one."""

    def __init__(self, projstore):
        self.store = projstore

    def convert_forward(self, sourcefile):
        self.store.transfiles.append('converted.po')

    def get_file(self, name):
        return SimpleNamespace(name='/tmp/' + name)


def _patch_project(monkeypatch, store):
    import virtaal.support.bundleprojstore as bundleprojstore
    import virtaal.support.project as project
    monkeypatch.setattr(bundleprojstore, 'BundleProjectStore', lambda filename: store)
    monkeypatch.setattr(project, 'Project', _FakeProject)
    return bundleprojstore


def test_open_file_via_bundle_loads_the_projects_first_transfile(monkeypatch):
    _patch_project(monkeypatch, SimpleNamespace(transfiles=['doc.po'], sourcefiles=[]))
    controller = _open_file_controller(monkeypatch, units=[object()])

    controller.open_file('bundle.zip')

    assert controller.real_filename == '/tmp/doc.po'
    assert controller.force_saveas_calls == [False]


def test_open_file_via_bundle_converts_the_first_source_file_when_none_exists(monkeypatch):
    store = SimpleNamespace(transfiles=[], sourcefiles=['doc.odt'])
    _patch_project(monkeypatch, store)
    controller = _open_file_controller(monkeypatch, units=[object()])

    controller.open_file('bundle.zip')

    assert store.transfiles == ['converted.po']
    assert controller.real_filename == '/tmp/converted.po'


def test_open_file_via_bundle_raises_when_nothing_to_convert(monkeypatch):
    bundleprojstore = _patch_project(monkeypatch, SimpleNamespace(transfiles=[], sourcefiles=[]))
    controller = _open_file_controller(monkeypatch, units=[])

    with pytest.raises(bundleprojstore.InvalidBundleError):
        controller.open_file('bundle.zip')


def test_revert_file_reopens_the_current_store_filename():
    controller = _controller()
    controller.store = SimpleNamespace(filename="/path/to/file.po")
    opened = []
    controller.open_file = opened.append

    controller.revert_file()

    assert opened == ["/path/to/file.po"]


# save_file() - plain (non-project) path #

def test_save_file_plain_saves_and_marks_clean():
    controller = _controller()
    controller.project = None
    prepared = []
    controller._unit_controller = SimpleNamespace(prepare_for_save=lambda: prepared.append(True))
    saved = []
    controller.store = SimpleNamespace(save_file=saved.append)
    controller._modified = True
    marked_clean = []
    controller.main_controller = SimpleNamespace(
        undo_controller=SimpleNamespace(
            model=SimpleNamespace(mark_clean=lambda: marked_clean.append(True))
        ),
        set_saveable=lambda v: None,
    )
    emitted = []
    controller.connect('store-saved', lambda *_: emitted.append(True))

    controller.save_file('out.po')

    assert prepared == [True]
    assert saved == ['out.po']
    assert controller._modified is False
    assert marked_clean == [True]
    assert emitted == [True]


# save_file() - project path #

def test_save_file_project_opens_the_real_file_in_binary_mode(tmp_path):
    real_file = tmp_path / 'source.po'
    real_file.write_bytes((
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '\nmsgid "coffee"\nmsgstr "café ☕"\n'
    ).encode())

    controller = _controller()
    controller.project = SimpleNamespace(
        get_proj_filename=lambda fname: 'trans/source.po',
        update_file=lambda proj_fname, infile: updated.update(
            proj_fname=proj_fname, mode=infile.mode, content=infile.read()
        ),
        convert_forward=lambda *a, **k: None,
        save=lambda: None,
    )
    updated = {}
    controller.real_filename = str(real_file)
    controller._unit_controller = SimpleNamespace(prepare_for_save=lambda: None)
    controller.store = SimpleNamespace(save_file=lambda: None)
    controller.main_controller = SimpleNamespace(
        undo_controller=SimpleNamespace(model=SimpleNamespace(mark_clean=lambda: None)),
        set_saveable=lambda v: None,
    )

    controller.save_file()

    assert updated['proj_fname'] == 'trans/source.po'
    assert updated['mode'] == 'rb'
    assert updated['content'] == real_file.read_bytes()


# binary_export() #

def test_binary_export_writes_the_compiled_store(monkeypatch, tmp_path):
    calls = []

    class _FakeCompiler:
        def convertstore(self, trans_store):
            calls.append(trans_store)
            return b'compiled-bytes'

    monkeypatch.setattr('translate.tools.pocompile.POCompile', _FakeCompiler)
    controller = _controller()
    trans_store = object()
    controller.store = SimpleNamespace(_trans_store=trans_store)
    outfile = tmp_path / "out.mo"

    controller.binary_export(str(outfile))

    assert calls == [trans_store]
    assert outfile.read_bytes() == b'compiled-bytes'


# update_file() #

def test_update_file_opens_a_new_file_when_none_is_open():
    controller = _controller()
    controller.store = None
    opened = []
    controller.open_file = lambda filename, uri='': opened.append((filename, uri))

    controller.update_file("new.po", uri="file:///new.po")

    assert opened == [("new.po", "file:///new.po")]


def test_update_file_replaces_the_cursor_on_an_already_open_store():
    # Regression: this method did "from cursor import Cursor" (missing the
    # leading dot) - a real, always-broken ModuleNotFoundError whenever a
    # store was already open, silently swallowed by MainController.update_file's
    # broad except-and-show-error handler.
    controller = _controller()
    controller.store = SimpleNamespace(
        update_file=lambda filename: None,
        stats={'total': [1, 2]},
    )
    saveable_calls = []
    saveas_calls = []
    controller.main_controller = SimpleNamespace(
        set_saveable=saveable_calls.append,
        set_force_saveas=saveas_calls.append,
    )
    shown = []
    controller._view = SimpleNamespace(
        load_store=shown.append,
        show=lambda: shown.append('shown'),
    )
    emitted = []
    controller.connect('store-loaded', lambda *_: emitted.append(True))

    controller.update_file("updated.po")

    assert controller._modified is True
    assert saveable_calls == [True]
    # Unlike open_file() with a bare .pot, updating an already-open file
    # keeps saving to its existing path - no forced Save As (#3808).
    assert saveas_calls == []
    assert controller.cursor.model is controller.store
    assert shown == [None, controller.store, 'shown']
    assert emitted == [True]


# update_store_checks() #

def test_update_store_checks_raises_without_a_store():
    controller = _controller()
    with pytest.raises(ValueError):
        controller.update_store_checks()


def test_update_store_checks_delegates_to_the_store():
    controller = _controller()
    calls = []
    controller.store = SimpleNamespace(update_checks=lambda **kw: calls.append(kw) or 'updated')

    result = controller.update_store_checks(quick=True)

    assert result == 'updated'
    assert calls == [{'quick': True}]


# compare_stats() #

def test_compare_stats_shows_before_and_after_counts():
    # A dismissable notice, not a blocking modal (#3808).
    controller = _controller()
    shown = []
    controller.main_controller = SimpleNamespace(show_template_update_notice=lambda title, msg: shown.append((title, msg)))
    oldstats = {'translated': [1], 'fuzzy': [1, 2], 'untranslated': []}
    newstats = {'translated': [1, 2, 3], 'fuzzy': [], 'untranslated': [1]}

    controller.compare_stats(oldstats, newstats)

    assert len(shown) == 1
    title, message = shown[0]
    assert title == "File Updated"
    assert message.count('1') >= 1  # old translated/fuzzy counts appear
    assert '3' in message  # new translated count appears


# event handlers #

def test_on_controller_registered_wires_up_lang_signals_once():
    controller = _controller()
    disconnected = []

    class _MainController:
        def __init__(self):
            self.lang_controller = SimpleNamespace(connections=[])

        def disconnect(self, handler_id):
            disconnected.append(handler_id)

        def connect(self, *_a, **_kw):  # lang_controller.connect below
            pass

    main_controller = _MainController()
    main_controller.lang_controller.connect = lambda sig, cb: main_controller.lang_controller.connections.append((sig, cb))
    controller._controller_register_id = 'reg-id'

    controller._on_controller_registered(main_controller, main_controller.lang_controller)

    assert disconnected == ['reg-id']
    assert main_controller.lang_controller.connections == [
        ('source-lang-changed', controller._on_source_lang_changed),
        ('target-lang-changed', controller._on_target_lang_changed),
    ]


def test_on_controller_registered_ignores_other_controllers():
    controller = _controller()

    class _MainController:
        lang_controller = object()

        def disconnect(self, handler_id):
            raise AssertionError("must not disconnect for an unrelated controller")

    controller._on_controller_registered(_MainController(), object())  # must not raise


def test_on_source_lang_changed_updates_the_store():
    controller = _controller()
    calls = []
    controller.store = SimpleNamespace(set_source_language=calls.append)

    controller._on_source_lang_changed(None, 'af')

    assert calls == ['af']


def test_on_target_lang_changed_updates_the_store():
    controller = _controller()
    calls = []
    controller.store = SimpleNamespace(set_target_language=calls.append)

    controller._on_target_lang_changed(None, 'af')

    assert calls == ['af']


# _unit_modified() #

def test_unit_modified_ignores_a_signal_with_no_store_open():
    controller = _controller()
    controller.store = None

    controller._unit_modified(None, object())  # must not raise


def test_unit_modified_ignores_a_unit_from_a_replaced_store():
    controller = _controller()
    controller.store = SimpleNamespace(get_units=lambda: [])
    modified_calls = []
    controller.set_modified = modified_calls.append

    controller._unit_modified(None, object())

    assert modified_calls == []


def test_unit_modified_marks_the_store_modified():
    controller = _controller()
    unit = object()
    controller.store = SimpleNamespace(get_units=lambda: [unit])
    modified_calls = []
    controller.set_modified = modified_calls.append

    controller._unit_modified(None, unit)

    assert modified_calls == [True]
