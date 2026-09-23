#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

# --- Ported from translate-toolkit ---
# Adapted from translate-toolkit (PyPI: translate-toolkit)'s own test
# suite for this module before its removal, file
# translate/storage/test_statsdb.py, at:
#   repo:      https://github.com/translate/translate
#   tag:       2.5.1
#   commit:    1dc4f89bdb35edc71177eb23533764b06532db11
# Rewritten to pytest-style (tmp_path, plain functions) rather than the
# original xunit-style setup_method()/teardown_method() class, and
# with the original's own cache.close() calls dropped: StatsCache.close()
# clears the *entire* class-level cache pool (every thread, every
# statsfile, not just this instance's), which killed the real default
# cache other tests in this same suite share for the rest of the run.

import os.path

from translate.filters import checks
from translate.storage import factory

from virtaal.support import statsdb

FR_TERMINOLOGY_EXTRACT = r"""
msgid ""
msgstr ""
"Project-Id-Version: GnomeGlossary\n"
"POT-Creation-Date: 2002-05-22 23:40+0200\n"
"PO-Revision-Date: 2002-05-22 23:38+0200\n"
"Last-Translator: Christophe Merlet (RedFox) <christophe@merlet.net>\n"
"Language-Team: GNOME French Team <gnomefr@traduc.org>\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=ISO-8859-1\n"
"Content-Transfer-Encoding: 8bit\n"

#. "English Definition"
msgid "Term"
msgstr "Terme"

#. "To terminate abruptly a processing activity in a computer system because it is impossible or undesirable for the activity to procees."
msgid "abort"
msgstr "annuler"
"""

JTOOLKIT_EXTRACT = r"""
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2005-06-13 14:54-0500\n"
"PO-Revision-Date: 2007-05-04 19:54+0200\n"
"Last-Translator: F Wolff <friedel@translate.org.za>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"
"X-Generator: Pootle 1.0rc1\n"
"Generated-By: pygettext.py 1.5\n"

#: web/server.py:57
#, python-format
#, fuzzy
msgid "Login for %s"
msgstr "Meld aan vir %s"

#: web/server.py:91
msgid "Cancel this action and start a new session"
msgstr "Kanselleer hierdie aksie en begin 'n nuwe sessie"

#: web/server.py:92
msgid "Instead of confirming this action, log out and start from scratch"
msgstr "Meld af en begin op nuut eerder as om hierdie aksie te bevestig."

#: web/server.py:97
#, fuzzy
msgid "Exit application"
msgstr "Verlaat toepassing"

#: web/server.py:98
msgid "Exit this application and return to the parent application"
msgstr "Verlaat hierdie toepassing en gaan terug na die ouertoepassing"

#: web/server.py:105
msgid ", please confirm login"
msgstr ""
"""


def _setup_file_and_db(tmp_path, file_contents=FR_TERMINOLOGY_EXTRACT):
    cache = statsdb.StatsCache(str(tmp_path / "stats.db"))
    filename = tmp_path / "test.po"
    filename.write_text(file_contents)
    f = factory.getobject(str(filename))
    return f, cache


def test_getfileid_recache_cached_unit(tmp_path):
    checker = checks.UnitChecker()
    f, cache = _setup_file_and_db(tmp_path)

    cache.filestats(f.filename, checker)
    state = cache.recacheunit(f.filename, checker, f.units[1])

    assert state == ['translated', 'total']


def test_unitstats(tmp_path):
    f, cache = _setup_file_and_db(tmp_path, JTOOLKIT_EXTRACT)

    u = cache.unitstats(f.filename)

    assert u['sourcewordcount'] == [3, 8, 11, 2, 9, 3]


def test_filestats(tmp_path):
    f, cache = _setup_file_and_db(tmp_path, JTOOLKIT_EXTRACT)

    s = cache.filestats(f.filename, checks.UnitChecker())

    assert s['translated'] == [2, 3, 5]
    assert s['fuzzy'] == [1, 4]
    assert s['untranslated'] == [6]
    assert s['total'] == [1, 2, 3, 4, 5, 6]


def _fileid_row(cache, filename):
    cache.cur.execute("""
        SELECT fileid, st_mtime, st_size FROM files
        WHERE path=?;""", (os.path.realpath(filename),))
    return cache.cur.fetchone()


def test_if_cached_after_filestats(tmp_path):
    f, cache = _setup_file_and_db(tmp_path, JTOOLKIT_EXTRACT)

    cache.filestats(f.filename, checks.UnitChecker())

    assert _fileid_row(cache, f.filename) is not None


def test_if_cached_after_unitstats(tmp_path):
    f, cache = _setup_file_and_db(tmp_path, JTOOLKIT_EXTRACT)

    cache.unitstats(f.filename)

    assert _fileid_row(cache, f.filename) is not None


def test_singletonness(tmp_path):
    # Both calls share the same tmp_path, so the same statsfile path
    # resolves to the same cached StatsCache instance.
    f1, cache1 = _setup_file_and_db(tmp_path, JTOOLKIT_EXTRACT)
    f2, cache2 = _setup_file_and_db(tmp_path, FR_TERMINOLOGY_EXTRACT)

    assert cache1 == cache2
