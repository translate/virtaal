#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sqlite3
from types import SimpleNamespace

from virtaal.common.platform import platform
from virtaal.plugins import migration


def _plugin(tmp_path, poedit_exists=False, lokalize_rc_exists=False):
    plugin = migration.Plugin.__new__(migration.Plugin)
    plugin.internal_name = 'migration'
    plugin.poedit_dir = str(tmp_path / 'poedit')
    plugin.lokalize_rc = str(tmp_path / 'lokalizerc') if not lokalize_rc_exists else str(tmp_path / 'lokalizerc')
    plugin.lokalize_tm_dir = str(tmp_path / 'lokalize_tm')
    return plugin


# _has_anything_to_migrate() / _poedit_config_exists(): the cheap,
# parse-free gate for whether to prompt the user at all.

def test_has_anything_to_migrate_is_false_when_nothing_exists(tmp_path):
    plugin = _plugin(tmp_path)

    assert plugin._has_anything_to_migrate() is False


def test_has_anything_to_migrate_is_true_with_a_poedit_config(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', False)
    plugin = _plugin(tmp_path)
    (tmp_path / 'poedit').mkdir()
    (tmp_path / 'poedit' / 'config').write_text('')

    assert plugin._has_anything_to_migrate() is True


def test_has_anything_to_migrate_is_true_with_a_lokalize_rc(tmp_path):
    plugin = _plugin(tmp_path)
    (tmp_path / 'lokalizerc').write_text('')

    assert plugin._has_anything_to_migrate() is True


def test_has_anything_to_migrate_is_true_with_a_real_lokalize_tm_database(tmp_path):
    plugin = _plugin(tmp_path)
    (tmp_path / 'lokalize_tm').mkdir()
    (tmp_path / 'lokalize_tm' / 'project.db').write_text('')

    assert plugin._has_anything_to_migrate() is True


def test_has_anything_to_migrate_ignores_sqlite_journal_files(tmp_path):
    plugin = _plugin(tmp_path)
    (tmp_path / 'lokalize_tm').mkdir()
    (tmp_path / 'lokalize_tm' / 'project-journal.db').write_text('')

    assert plugin._has_anything_to_migrate() is False


def test_poedit_config_exists_true_for_the_macos_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'is_mac', True)
    plugin = _plugin(tmp_path)
    (tmp_path / 'poedit').mkdir()
    (tmp_path / 'poedit' / 'net.poedit.Poedit.cfg').write_text('')

    assert plugin._poedit_config_exists() is True


def test_poedit_config_exists_false_without_a_registry_on_windows(tmp_path, monkeypatch):
    # winreg doesn't exist on this (non-Windows) test host regardless
    # of the is_windows override - exercises the "no winreg module"
    # fallback rather than a real registry lookup.
    monkeypatch.setattr(platform, 'is_mac', False)
    monkeypatch.setattr(platform, 'is_windows', True)
    plugin = _plugin(tmp_path)

    assert plugin._poedit_config_exists() is False


# poedit_settings_import(): the headerless-INI parsing trick (Poedit's
# own config file has no [section] header at all).

def _poedit_plugin(tmp_path, content=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(platform, 'is_mac', False)
    plugin = _plugin(tmp_path)
    (tmp_path / 'poedit').mkdir()
    if content is not None:
        (tmp_path / 'poedit' / 'config').write_text(content)
    plugin.migrated = []
    return plugin


def test_poedit_settings_import_reads_the_headerless_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.pan_app.settings, 'general', {})
    monkeypatch.setattr(migration.pan_app.settings, 'translator', {})
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    plugin = _poedit_plugin(tmp_path, monkeypatch=monkeypatch, content=(
        'last_file_path = /tmp/project\n'
        'translator_name = Jane\n'
        'translator_email = jane@example.com\n'
    ))

    plugin.poedit_settings_import()

    assert migration.pan_app.settings.general['lastdir'] == '/tmp/project'
    assert migration.pan_app.settings.translator['name'] == 'Jane'
    assert migration.pan_app.settings.translator['email'] == 'jane@example.com'
    assert plugin.migrated == ['Poedit settings']


def test_poedit_settings_import_does_nothing_without_a_config_file_or_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    plugin = _poedit_plugin(tmp_path, monkeypatch=monkeypatch)

    plugin.poedit_settings_import()  # must not raise

    assert plugin.migrated == []


def test_poedit_settings_import_records_nothing_when_the_file_has_no_useful_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: (_ for _ in ()).throw(
        AssertionError('should not write with nothing to save')))
    plugin = _poedit_plugin(tmp_path, monkeypatch=monkeypatch, content='unrelated_key = value\n')

    plugin.poedit_settings_import()

    assert plugin.migrated == []


# lokalize_settings_import()

def test_lokalize_settings_import_reads_identity_and_last_project_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.pan_app.settings, 'general', {})
    monkeypatch.setattr(migration.pan_app.settings, 'translator', {})
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    plugin = _plugin(tmp_path)
    plugin.migrated = []
    (tmp_path / 'lokalizerc').write_text(
        '[Identity]\n'
        'AuthorName=Jane\n'
        'AuthorEmail=jane@example.com\n'
        'DefaultMailingList=team@example.com\n'
        '[State]\n'
        'Project=/home/jane/projects/foo/foo.lokalize\n'
    )

    plugin.lokalize_settings_import()

    assert migration.pan_app.settings.translator['name'] == 'Jane'
    assert migration.pan_app.settings.translator['email'] == 'jane@example.com'
    assert migration.pan_app.settings.translator['team'] == 'team@example.com'
    assert migration.pan_app.settings.general['lastdir'] == '/home/jane/projects/foo'
    assert plugin.migrated == ['Lokalize settings']


def test_lokalize_settings_import_does_nothing_without_an_rc_file(tmp_path):
    plugin = _plugin(tmp_path)
    plugin.migrated = []

    plugin.lokalize_settings_import()  # must not raise

    assert plugin.migrated == []


# lokalize_tm_import(): only "*.db" files that aren't sqlite's own
# "*-journal.db" companion are real Lokalize TM databases (a
# "*.remotedb" just points at a remote server, nothing local to read).

def test_lokalize_tm_import_only_passes_through_real_local_databases(tmp_path):
    plugin = _plugin(tmp_path)
    tm_dir = tmp_path / 'lokalize_tm'
    tm_dir.mkdir()
    for name in ('real.db', 'real-journal.db', 'remote.remotedb'):
        (tm_dir / name).write_text('')
    imported = []
    plugin.do_lokalize_tm_import = lambda filename: imported.append(filename)

    plugin.lokalize_tm_import()

    assert imported == [str(tm_dir / 'real.db')]


def test_lokalize_tm_import_does_nothing_without_the_tm_directory(tmp_path):
    plugin = _plugin(tmp_path)
    imported = []
    plugin.do_lokalize_tm_import = lambda filename: imported.append(filename)

    plugin.lokalize_tm_import()  # must not raise

    assert imported == []


# do_lokalize_tm_import(): Lokalize's own normalized schema
# (source_strings/target_strings/main) and tm_config fallbacks.

def _lokalize_db(tmp_path, name='project.db', with_config=True, with_rows=True):
    db_path = tmp_path / name
    connection = sqlite3.connect(str(db_path))
    connection.execute('CREATE TABLE tm_config (key INTEGER, value TEXT)')
    connection.execute('CREATE TABLE source_strings (id INTEGER PRIMARY KEY, source TEXT)')
    connection.execute('CREATE TABLE target_strings (id INTEGER PRIMARY KEY, target TEXT)')
    connection.execute('CREATE TABLE main (source INTEGER, target INTEGER)')
    if with_config:
        connection.execute('INSERT INTO tm_config VALUES (2, "en")')
        connection.execute('INSERT INTO tm_config VALUES (3, "af")')
    if with_rows:
        connection.execute("INSERT INTO source_strings VALUES (1, 'Hello')")
        connection.execute("INSERT INTO target_strings VALUES (1, 'Hallo')")
        connection.execute('INSERT INTO main VALUES (1, 1)')
    connection.commit()
    connection.close()
    return str(db_path)


class _FakeTMDB:
    def __init__(self):
        self.added = []
        self.committed = False
        self.connection = SimpleNamespace(commit=lambda: setattr(self, 'committed', True))

    def add_dict(self, unit, source_lang, target_lang, commit=False):
        self.added.append((unit, source_lang, target_lang))


def test_do_lokalize_tm_import_reads_units_and_language_codes(tmp_path):
    db_path = _lokalize_db(tmp_path)
    plugin = _plugin(tmp_path)
    plugin.tmdb = _FakeTMDB()
    plugin.migrated = []

    plugin.do_lokalize_tm_import(db_path)

    assert plugin.tmdb.added == [
        ({'source': 'Hello', 'target': 'Hallo', 'context': ''}, 'en', 'af'),
    ]
    assert plugin.tmdb.committed is True
    assert plugin.migrated == [
        "Lokalize's Translation Memory: %(database_name)s" % {'database_name': 'project.db'},
    ]


def test_do_lokalize_tm_import_falls_back_when_tm_config_is_missing(tmp_path):
    db_path = _lokalize_db(tmp_path, with_config=False)
    plugin = _plugin(tmp_path)
    plugin.tmdb = _FakeTMDB()
    plugin.migrated = []
    plugin.main_controller = SimpleNamespace(
        lang_controller=SimpleNamespace(target_lang=SimpleNamespace(code='fr')))

    plugin.do_lokalize_tm_import(db_path)

    (unit, source_lang, target_lang) = plugin.tmdb.added[0]
    assert source_lang == 'en'
    assert target_lang == 'fr'


def test_do_lokalize_tm_import_records_nothing_for_an_empty_database(tmp_path):
    db_path = _lokalize_db(tmp_path, with_rows=False)
    plugin = _plugin(tmp_path)
    plugin.tmdb = _FakeTMDB()
    plugin.migrated = []

    plugin.do_lokalize_tm_import(db_path)

    assert plugin.tmdb.added == []
    assert plugin.tmdb.committed is False
    assert plugin.migrated == []


def test_do_lokalize_tm_import_closes_the_connection_even_if_the_query_fails(tmp_path):
    # An older/unexpected schema shouldn't leave the sqlite connection
    # (and its file lock) open behind a raised exception.
    db_path = tmp_path / 'broken.db'
    connection = sqlite3.connect(str(db_path))
    connection.execute('CREATE TABLE unrelated (x INTEGER)')
    connection.commit()
    connection.close()
    plugin = _plugin(tmp_path)
    plugin.tmdb = _FakeTMDB()
    plugin.migrated = []

    try:
        plugin.do_lokalize_tm_import(str(db_path))
        assert False, 'expected the missing-table query to raise'
    except sqlite3.OperationalError:
        pass

    # A closed connection raises ProgrammingError on any further use.
    try:
        connection2 = sqlite3.connect(str(db_path))
        connection2.close()
        connection2.execute('SELECT 1')
        assert False, 'expected use-after-close to raise'
    except sqlite3.ProgrammingError:
        pass


# _init_plugin(): the overall migrate-or-stay-silent orchestration.

def _plugin_for_init(tmp_path, has_anything, accepts=True):
    plugin = _plugin(tmp_path)
    plugin.config = {'tmdb': str(tmp_path / 'tm.db')}
    plugin._has_anything_to_migrate = lambda: has_anything
    prompted = []
    shown = []
    plugin.main_controller = SimpleNamespace(
        show_prompt=lambda title, message: prompted.append((title, message)) or accepts,
        show_info=lambda title, message: shown.append((title, message)),
    )
    plugin._prompted = prompted
    plugin._shown = shown
    return plugin


def test_init_plugin_disables_itself_silently_with_nothing_to_migrate(tmp_path, monkeypatch):
    disabled = {}
    monkeypatch.setattr(migration.pan_app.settings, 'plugin_state', disabled)
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    plugin = _plugin_for_init(tmp_path, has_anything=False)

    plugin._init_plugin()

    assert plugin._prompted == []
    assert disabled['migration'] == 'disabled'


def test_init_plugin_disables_without_migrating_when_the_user_declines(tmp_path, monkeypatch):
    disabled = {}
    monkeypatch.setattr(migration.pan_app.settings, 'plugin_state', disabled)
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    plugin = _plugin_for_init(tmp_path, has_anything=True, accepts=False)
    plugin.poedit_settings_import = lambda: (_ for _ in ()).throw(AssertionError('should not migrate'))

    plugin._init_plugin()

    assert len(plugin._prompted) == 1
    assert plugin._shown == []
    assert disabled['migration'] == 'disabled'


def test_init_plugin_shows_a_summary_of_what_was_migrated(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.pan_app.settings, 'plugin_state', {})
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    monkeypatch.setattr(migration.tmdb, 'TMDB', lambda path: SimpleNamespace())
    plugin = _plugin_for_init(tmp_path, has_anything=True, accepts=True)
    plugin.poedit_settings_import = lambda: plugin.migrated.append('Poedit settings')
    plugin.lokalize_settings_import = lambda: None
    plugin.lokalize_tm_import = lambda: None

    plugin._init_plugin()

    assert len(plugin._shown) == 1
    title, message = plugin._shown[0]
    assert title == 'Migration completed'
    assert 'Poedit settings' in message


def test_init_plugin_shows_nothing_migrated_when_all_imports_find_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.pan_app.settings, 'plugin_state', {})
    monkeypatch.setattr(migration.pan_app.settings, 'write', lambda: None)
    monkeypatch.setattr(migration.tmdb, 'TMDB', lambda path: SimpleNamespace())
    plugin = _plugin_for_init(tmp_path, has_anything=True, accepts=True)
    plugin.poedit_settings_import = lambda: None
    plugin.lokalize_settings_import = lambda: None
    plugin.lokalize_tm_import = lambda: None

    plugin._init_plugin()

    assert plugin._shown == [('Nothing migrated', 'Virtaal was not able to migrate any settings or data')]
