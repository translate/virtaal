#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from translate.filters import checks
from translate.misc.multistring import multistring
from translate.storage import factory

from virtaal.models.storemodel import StoreModel
from virtaal.support import statsdb


def test_load_file_with_an_empty_source_string(tmp_path):
    # translate/virtaal#3249: an empty <source></source> in a .ts file
    # parses with unit.source == None, which used to crash statsdb's
    # own "source VARCHAR NOT NULL" constraint on load.
    ts_file = tmp_path / "empty_source.ts"
    ts_file.write_text("""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS language="da">
<context>
<name>Test</name>
<message>
<source></source>
<translation>foo</translation>
</message>
</context>
</TS>
""")
    model = StoreModel(str(ts_file), None)
    assert len(model) == 1


# wordsinunit() #

def test_wordsinunit_counts_every_plural_form():
    # multistring.strings puts the multistring itself first (which
    # counts as its own primary form) followed by the remaining plural
    # forms, so the primary form is counted once via that first
    # element - not double, just not obviously so from the plain
    # string list alone.
    unit = SimpleNamespace(
        source=multistring(['one word', 'two words here']),
        target=multistring(['single', 'three words total']),
        istranslated=lambda: True,
    )

    sourcewords, targetwords = statsdb.wordsinunit(unit)

    assert sourcewords == 2 + 3  # "one word" + "two words here"
    assert targetwords == 1 + 3  # "single" + "three words total"


# transaction() #

def test_transaction_rolls_back_and_reraises_on_failure():
    rolled_back = []
    committed = []

    class _FakeCache:
        con = SimpleNamespace(commit=lambda: committed.append(True),
                               rollback=lambda: rolled_back.append(True))

        @statsdb.transaction
        def boom(self):
            raise ValueError('failed mid-transaction')

    with pytest.raises(ValueError, match='failed mid-transaction'):
        _FakeCache().boom()

    assert rolled_back == [True]
    assert committed == []


# FileTotals / emptyfilechecks() #

def test_file_totals_delitem_removes_the_row(tmp_path):
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    cache.file_totals[1] = statsdb.FileTotals.new_record()

    del cache.file_totals[1]

    assert cache.file_totals[1].to_tuple() == statsdb.FileTotals.new_record().to_tuple()


def test_emptyfilechecks_is_empty():
    assert statsdb.emptyfilechecks() == {}


def test_emptyfiletotals_is_all_zero():
    totals = statsdb.emptyfiletotals()

    assert totals['total'] == 0
    assert totals['totalsourcewords'] == 0


# file_extended_totals() / filetotals(extended=True) #

def test_file_extended_totals_breaks_down_by_state(tmp_path):
    po_content = (
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Bonjour"\n\n'
        'msgid "World"\nmsgstr ""\n'
    )
    po_file = tmp_path / "test.po"
    po_file.write_text(po_content)
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    store = factory.getobject(str(po_file))

    stats = cache.file_extended_totals(str(po_file), store=store)

    assert stats['unreviewed']['units'] == 1
    assert stats['empty']['units'] == 1


def test_filetotals_with_extended_includes_the_breakdown(tmp_path):
    po_file = tmp_path / "test.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Bonjour"\n')
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    store = factory.getobject(str(po_file))

    totals = cache.filetotals(str(po_file), store=store, extended=True)

    assert 'extended' in totals
    assert totals['extended']['unreviewed']['units'] == 1


# get_unit_stats() #

def test_get_unit_stats_warns_and_returns_empty_for_an_unknown_unit(tmp_path, caplog):
    import logging
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))

    with caplog.at_level(logging.WARNING):
        result = cache.get_unit_stats(999, 'no-such-unit')

    assert result == []
    assert any('inconsistent state' in r.message for r in caplog.records)


# file_fails_test() #

def test_file_fails_test_finds_the_dummy_noerror_entry(tmp_path):
    po_file = tmp_path / "test.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Bonjour"\n')
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    checker = checks.UnitChecker()

    assert cache.file_fails_test(str(po_file), checker, 'noerror') is True
    assert cache.file_fails_test(str(po_file), checker, 'nonexistent-check') is False


# _getfileid()'s remaining branches #

def test_getfileid_accepts_a_bytes_filename(tmp_path):
    po_file = tmp_path / "test.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Bonjour"\n')
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))

    fileid = cache._getfileid(str(po_file).encode())

    assert fileid is not None


def test_getfileid_calls_a_callable_store(tmp_path):
    po_file = tmp_path / "test.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Bonjour"\n')
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    calls = []

    def make_store():
        calls.append(True)
        return factory.getobject(str(po_file))

    cache._getfileid(str(po_file), store=make_store)

    assert calls == [True]


# close() #

def test_close_closes_every_cached_connection(tmp_path):
    # Swap out the real, shared class-level cache pool for the
    # duration of this test - close() iterates and closes *every*
    # cached connection process-wide, not just this instance's, and
    # the real pool is shared with the rest of this test session.
    #
    # Note: close()'s own `self._caches = {}` sets an *instance*
    # attribute, shadowing rather than clearing the class-level dict
    # __new__() actually reads from - the registry entry (now pointing
    # at a closed, unusable connection) is never actually removed.
    # This is real, vendored-as-is upstream behaviour (see this
    # module's own copyright banner), not something to fix here.
    original_caches = statsdb.StatsCache._caches
    statsdb.StatsCache._caches = {}
    try:
        cache = statsdb.StatsCache(str(tmp_path / "stats.db"))

        cache.close()

        with pytest.raises(statsdb.dbapi2.ProgrammingError):
            cache.cur.execute("SELECT 1")
    finally:
        statsdb.StatsCache._caches = original_caches
