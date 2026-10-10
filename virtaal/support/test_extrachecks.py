#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from translate.filters import checks
from translate.filters.decorators import Category
from translate.storage import po, ts2

from virtaal.support import extrachecks, gettextpo, statsdb

HEADER = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

'''
BAD_C_FORMAT = b'#, c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n'


class LengthCheck:
    name = 'toolong'
    category = Category.COSMETIC

    @staticmethod
    def applies_to(store):
        return True

    @staticmethod
    def available():
        return True

    def check(self, unit):
        return 'Too long' if len(str(unit.target)) > 5 else None


class UnavailableCheck(LengthCheck):
    name = 'unavailable'

    @staticmethod
    def available():
        return False


@pytest.fixture
def length_check_only(monkeypatch):
    monkeypatch.setattr(extrachecks, 'EXTRA_CHECKS', [LengthCheck, UnavailableCheck])


def test_filter_adds_failures(length_check_only):
    store = po.pofile.parsestring(HEADER + b'msgid "a"\nmsgstr "abcdefg"\n')
    checker = extrachecks.with_extra_checks(checks.StandardChecker(), store)

    failures = checker.run_filters(store.units[-1])

    assert failures['toolong'] == 'Too long'
    assert 'unavailable' not in failures


def test_filter_categorised(length_check_only):
    store = po.pofile.parsestring(HEADER + b'msgid "a"\nmsgstr "abcdefg"\n')
    checker = extrachecks.with_extra_checks(checks.StandardChecker(), store)

    failures = checker.run_filters(store.units[-1], categorised=True)

    assert failures['toolong'] == {'message': 'Too long', 'category': Category.COSMETIC}


def test_no_wrapper_without_extra_checks(monkeypatch):
    monkeypatch.setattr(extrachecks, 'EXTRA_CHECKS', [UnavailableCheck])
    inner = checks.StandardChecker()

    assert extrachecks.with_extra_checks(inner, po.pofile()) is inner


def test_filter_delegates_to_the_checker(length_check_only):
    inner = checks.StandardChecker()
    checker = extrachecks.with_extra_checks(inner, po.pofile())

    assert checker.config is inner.config


@pytest.mark.skipif(not gettextpo.available(), reason="libgettextpo is not available")
def test_msgfmt_is_registered():
    store = po.pofile.parsestring(HEADER + BAD_C_FORMAT)
    checker = extrachecks.with_extra_checks(checks.StandardChecker(), store)

    failures = checker.run_filters(store.units[-1])

    assert 'format specifications' in failures['msgfmt']
    assert 'printf' in failures
    assert extrachecks.with_extra_checks(checks.StandardChecker(), ts2.tsfile()).__class__ is checks.StandardChecker


def test_statsdb_does_not_reuse_checks_cached_without_extra_checks(tmp_path, length_check_only):
    po_file = tmp_path / "test.po"
    po_file.write_bytes(HEADER + b'msgid "a"\nmsgstr "abcdefg"\n')
    store = po.pofile.parsefile(str(po_file))
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))

    plain = cache.filechecks(str(po_file), checks.StandardChecker(), store)
    extra = cache.filechecks(str(po_file), extrachecks.with_extra_checks(checks.StandardChecker(), store), store)

    assert 'check-toolong' not in plain
    assert extra['check-toolong'] == [1]
