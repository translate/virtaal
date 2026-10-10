#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import ctypes
import os
import re

import pytest
from translate.storage import po

from virtaal.support import gettextpo

pytestmark = pytest.mark.skipif(not gettextpo.available(),
                                reason="libgettextpo is not available")

HEADER = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

'''


def check(entry, header=HEADER):
    store = po.pofile.parsestring(header + entry)
    checker = gettextpo.MsgfmtChecker()
    checker.set_header(store.header().target)
    return checker.check_unit(store.units[-1])


def test_good():
    assert check(b'#, c-format\nmsgid "Hello %s"\nmsgstr "Hallo %s"\n') == []


def test_untranslated():
    assert check(b'#, c-format\nmsgid "Hello %s"\nmsgstr ""\n') == []


def test_c_format():
    problems = check(b'#, c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n')
    assert len(problems) == 1
    assert "format specifications" in problems[0]


def test_no_format_flag():
    assert check(b'msgid "Hello %s"\nmsgstr "Hallo"\n') == []
    assert check(b'#, no-c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n') == []


def test_python_format():
    problems = check(b'#, python-format\nmsgid "%(name)s"\nmsgstr "%(naam)s"\n')
    assert len(problems) == 1
    assert "naam" in problems[0]


def test_fuzzy_is_checked():
    assert check(b'#, fuzzy, c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n')


def test_newlines():
    problems = check(b'msgid "line\\n"\nmsgstr "lyn"\n')
    assert len(problems) == 1
    assert "\\n" in problems[0]


def test_plural_format():
    entry = (b'#, c-format\nmsgid "one %d"\nmsgid_plural "many %d"\n'
             b'msgstr[0] "een"\nmsgstr[1] "baie %s"\n')
    problems = check(entry)
    assert len(problems) == 1
    assert "msgstr[1]" in problems[0]


def test_plural_count():
    entry = (b'msgid "one"\nmsgid_plural "many"\n'
             b'msgstr[0] "een"\nmsgstr[1] "baie"\n')
    assert check(entry) == []
    header = HEADER.replace(b"nplurals=2; plural=(n != 1)",
                            b"nplurals=3; plural=(n==1 ? 0 : n==2 ? 1 : 2)")
    assert check(entry, header)


def test_header_problems_only_on_header():
    store = po.pofile.parsestring(HEADER + b'msgid "a"\nmsgstr "b"\n')
    checker = gettextpo.MsgfmtChecker()
    assert checker.check_unit(store.units[0])
    assert checker.check_unit(store.units[1]) == []



def test_msgfmt_check_uses_the_units_store_header():
    entry = (b'msgid "one"\nmsgid_plural "many"\n'
             b'msgstr[0] "een"\nmsgstr[1] "baie"\n')
    header = HEADER.replace(b"nplurals=2; plural=(n != 1)",
                            b"nplurals=3; plural=(n==1 ? 0 : n==2 ? 1 : 2)")
    check = gettextpo.MsgfmtCheck()

    assert check.check(po.pofile.parsestring(HEADER + entry).units[-1]) is None
    assert check.check(po.pofile.parsestring(header + entry).units[-1])


def test_msgfmt_check_applies_to_po_only():
    from translate.storage import ts2

    assert gettextpo.MsgfmtCheck.applies_to(po.pofile())
    assert not gettextpo.MsgfmtCheck.applies_to(ts2.tsfile())


def test_bundled_library_only(tmp_path, monkeypatch):
    from virtaal.common.platform import Platform
    bundle_dir = tmp_path / "Contents" / "MacOS"
    bundle_dir.mkdir(parents=True)
    frameworks = tmp_path / "Contents" / "Frameworks"
    frameworks.mkdir()
    (frameworks / "libgettextpo.0.dylib").touch()
    monkeypatch.setattr(gettextpo, 'platform',
                        Platform(sys_platform='darwin', frozen=True, executable=str(bundle_dir / "virtaal")))

    assert list(gettextpo._library_candidates()) == [str(frameworks / "libgettextpo.0.dylib")]


REFERENCE = os.path.join(os.path.dirname(__file__), '..', '..', 'devsupport', 'testfiles', 'msgfmt.po')


def _gettext_version():
    return ctypes.c_int.in_dll(gettextpo._load_library(), 'libgettextpo_version').value


def test_reference_file_gets_the_noted_messages():
    # devsupport/testfiles/msgfmt.po notes gettext 1.0's messages; other
    # versions word, and sometimes judge, them differently.
    if _gettext_version() >> 8 != 0x0100:
        pytest.skip("libgettextpo isn't gettext 1.0")
    store = po.pofile.parsefile(REFERENCE)
    check = gettextpo.MsgfmtCheck()
    prefix = "Expected 'msgfmt': "
    for unit in store.units[1:]:
        expected = re.sub(r" \(the translation holds [^)]*\)", "", unit.getnotes('developer'))
        assert expected.startswith(prefix)
        assert (check.check(unit) or '').replace('\n', ' / ') == expected[len(prefix):], str(unit.source)
