#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The local TM server's database, against real SQLite files. Failures
come from SQLite itself: an authorizer refuses the statement."""

import logging
import sqlite3

import pytest
from translate.storage import base, xliff

from virtaal.support import tmdb

LONG = 'Open the selected translation file'  # Over 3 words: full-text search.
SHORT = 'Open it'


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / 'tm.db')
    yield path
    # TMDB shares one connection per file and thread for the whole process.
    for connection, _cursor in tmdb.TMDB._tm_dbs.pop(path, {}).values():
        connection.close()


def _allow(*args):
    # Python 3.10 ignores set_authorizer(None): it keeps the old authorizer.
    return sqlite3.SQLITE_OK


def _refuse(*denied):
    """An authorizer refusing (action, table) pairs; table None means any."""
    def authorize(action, arg1, arg2, db_name, trigger):
        if (action, arg1) in denied or (action, None) in denied:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return authorize


@pytest.fixture
def refusing_connect(monkeypatch):
    """Make the next connections TMDB opens refuse some statements."""
    def refuse(*denied):
        connect = sqlite3.dbapi2.connect
        def connect_refusing(*args, **kwargs):
            connection = connect(*args, **kwargs)
            connection.set_authorizer(_refuse(*denied))
            return connection
        monkeypatch.setattr(tmdb.dbapi2, 'connect', connect_refusing)
    return refuse


def _count(db, table):
    return db.cursor.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]


def _xliff_unit(source, target, source_lang='en', target_lang='af'):
    store = xliff.xlifffile(sourcelanguage=source_lang, targetlanguage=target_lang)
    unit = store.addsourceunit(source)
    unit.target = target
    return unit


def test_a_database_path_that_isnt_a_string_is_opened(tmp_path):
    path = tmp_path / 'tm.db'
    try:
        db = tmdb.TMDB(path)

        assert db.db_file == str(path)
        assert path.exists()
    finally:
        for connection, _cursor in tmdb.TMDB._tm_dbs.pop(str(path), {}).values():
            connection.close()


def test_a_failed_schema_setup_raises_and_leaves_the_connection_usable(db_path, refusing_connect):
    refusing_connect((sqlite3.SQLITE_CREATE_TABLE, None))

    with pytest.raises(sqlite3.DatabaseError):
        tmdb.TMDB(db_path)

    # Rolled back: the shared connection isn't left in a failed transaction.
    connection, cursor = next(iter(tmdb.TMDB._tm_dbs[db_path].values()))
    connection.set_authorizer(_allow)
    assert cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []
    db = tmdb.TMDB(db_path)
    db.add_dict({'source': SHORT, 'target': 'Maak dit oop', 'context': ''}, 'en', 'af')
    assert db.translate_unit(SHORT, 'en', 'af')[0]['target'] == 'Maak dit oop'


def test_reopening_a_database_reuses_its_fulltext_index(db_path):
    first = tmdb.TMDB(db_path)
    first.add_dict({'source': LONG, 'target': 'Maak die gekose lêer oop', 'context': ''}, 'en', 'af')

    second = tmdb.TMDB(db_path)

    assert second.fulltext
    assert second.translate_unit(LONG, 'en', 'af')[0]['target'] == 'Maak die gekose lêer oop'
    assert second.preload_db() == 1


class _CursorWithoutFts3(sqlite3.Cursor):
    """What SQLite built without the FTS3 module says to an FTS3 table."""
    def executescript(self, script):
        if 'USING fts3' in script:
            raise sqlite3.OperationalError('no such module: fts3')
        return super().executescript(script)


class _ConnectionWithoutFts3(sqlite3.Connection):
    def cursor(self, factory=_CursorWithoutFts3):
        return super().cursor(factory)


def test_without_fts3_the_database_falls_back_to_plain_search(db_path, monkeypatch, caplog):
    # A database made where FTS3 works, then opened where it doesn't.
    tmdb.TMDB(db_path)
    for connection, _cursor in tmdb.TMDB._tm_dbs.pop(db_path).values():
        connection.close()
    connect = sqlite3.dbapi2.connect
    monkeypatch.setattr(tmdb.dbapi2, 'connect', lambda path: connect(path, factory=_ConnectionWithoutFts3))

    with caplog.at_level(logging.ERROR, logger=tmdb.logger.name):
        db = tmdb.TMDB(db_path)

    assert not db.fulltext
    assert 'failed to initialize fts3 support' in caplog.text
    # They would write to the full-text index.
    assert db.cursor.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'").fetchall() == []
    db.add_dict({'source': LONG, 'target': 'Maak die gekose lêer oop', 'context': ''}, 'en', 'af')
    assert db.translate_unit(LONG, 'en', 'af')[0]['target'] == 'Maak die gekose lêer oop'
    assert db.preload_db() == 1


def test_add_unit_takes_the_languages_from_the_units_file(db_path):
    db = tmdb.TMDB(db_path)

    db.add_unit(_xliff_unit(SHORT, 'Maak dit oop', 'en', 'af'))

    assert db.translate_unit(SHORT, 'en', 'af')[0]['target'] == 'Maak dit oop'


@pytest.mark.parametrize(('source_lang', 'target_lang', 'message'), [
    (None, 'af', 'undefined source language'),
    ('en', None, 'undefined target language'),
])
def test_add_unit_needs_both_languages(db_path, source_lang, target_lang, message):
    # A unit without a file has no languages of its own.
    unit = base.TranslationUnit(SHORT)
    unit.target = 'Maak dit oop'
    db = tmdb.TMDB(db_path)

    with pytest.raises(tmdb.LanguageError) as excinfo:
        db.add_unit(unit, source_lang, target_lang)

    assert str(excinfo.value) == message
    assert _count(db, 'sources') == 0


def test_a_failed_insert_rolls_back_the_whole_unit(db_path):
    db = tmdb.TMDB(db_path)
    db.connection.set_authorizer(_refuse((sqlite3.SQLITE_INSERT, 'targets')))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.add_dict({'source': SHORT, 'target': 'Maak dit oop', 'context': ''}, 'en', 'af')
    finally:
        db.connection.set_authorizer(_allow)

    assert _count(db, 'sources') == 0


def test_a_failed_insert_without_commit_leaves_rolling_back_to_the_caller(db_path):
    db = tmdb.TMDB(db_path)
    db.connection.set_authorizer(_refuse((sqlite3.SQLITE_INSERT, 'targets')))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.add_dict({'source': SHORT, 'target': 'Maak dit oop', 'context': ''}, 'en', 'af', commit=False)
    finally:
        db.connection.set_authorizer(_allow)

    # The source row is still in the open transaction, for the caller to undo.
    assert _count(db, 'sources') == 1
    db.connection.rollback()
    assert _count(db, 'sources') == 0


@pytest.mark.parametrize('source', [SHORT, LONG])
def test_translate_unit_matches_any_of_several_languages(db_path, source):
    db = tmdb.TMDB(db_path)
    db.add_dict({'source': source, 'target': 'Afrikaans', 'context': ''}, 'en_GB', 'af_ZA')

    matches = db.translate_unit(source, ['de', 'EN_gb'], ['zu', 'af-ZA'])

    assert [match['target'] for match in matches] == ['Afrikaans']
    assert db.translate_unit(source, ['de', 'fr'], ['af_ZA']) == []
