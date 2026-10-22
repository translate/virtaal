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


def test_lisp_format_with_a_huge_count_is_not_checked():
    # gettext 1.0 builds a list as long as the count: 10000000 needs over 1 GB.
    assert check(b'#, lisp-format\nmsgid "~{~1@*~D~}"\nmsgstr "~{~10000000@*~D~}"\n') == []
    assert check(b'#, scheme-format\nmsgid "~{~10000000*~D~}"\nmsgstr "~{~1*~D~}"\n') == []
    assert check(b'#, lisp-format\nmsgid "~D files"\nmsgstr "~A"\n')


def test_a_huge_number_is_checked_in_other_formats():
    assert check(b'#, c-format\nmsgid "%d of 1000000"\nmsgstr "1000000"\n')


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


def test_checked_messages_are_freed_with_the_rebuilt_file(monkeypatch):
    # libgettextpo has no po_message_free(): each message goes into the
    # checker's file, which is freed and rebuilt from its header.
    monkeypatch.setattr(gettextpo.MsgfmtChecker, 'REBUILD_AFTER', 3)
    store = po.pofile.parsestring(HEADER + b'#, c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n')
    checker = gettextpo.MsgfmtChecker()
    checker.set_header(store.header().target)
    frees = []
    original = checker._free
    checker._free = lambda: (frees.append(True), original())

    for _ in range(7):
        assert checker.check_unit(store.units[-1])

    assert len(frees) == 2


BAD_C_FORMAT = b'#, c-format\nmsgid "Hello %s"\nmsgstr "Hallo"\n'
C_FORMAT_PROBLEM = "number of format specifications in 'msgid' and 'msgstr' does not match"


def test_context_is_checked_with_its_message():
    assert check(b'#, c-format\nmsgctxt "menu"\nmsgid "Hello %s"\nmsgstr "Hallo"\n') == [C_FORMAT_PROBLEM]


def test_check_without_a_header():
    store = po.pofile.parsestring(HEADER + BAD_C_FORMAT)

    assert gettextpo.MsgfmtChecker().check_unit(store.units[-1]) == [C_FORMAT_PROBLEM]


def test_a_problem_reported_outside_a_check_is_dropped():
    checker = gettextpo.MsgfmtChecker()

    checker._add_problem(b'not from a checked message')

    assert checker._problems is None


@pytest.fixture
def ui_languages(monkeypatch):
    # Not the real one: it would switch the whole test process's UI language.
    from virtaal.common import pan_app
    languages = []
    monkeypatch.setattr(pan_app, 'set_ui_language', languages.append)
    return languages


def test_self_check_reports_the_library_and_a_c_format_problem(ui_languages):
    # What the packaged builds' smoke tests run: the library they load,
    # and msgfmt's message in the UI language asked for.
    path, message = gettextpo.self_check('de')

    assert path == gettextpo._lib.path
    assert message
    assert ui_languages == ['de']


def _run_main(monkeypatch, *args):
    import runpy
    import sys
    monkeypatch.setattr(sys, 'argv', ['gettextpo', *args])
    # run_module() warns if the module is already imported.
    monkeypatch.delitem(sys.modules, 'virtaal.support.gettextpo')
    runpy.run_module('virtaal.support.gettextpo', run_name='__main__')


def test_run_module_prints_the_report(monkeypatch, capsys, ui_languages):
    _run_main(monkeypatch)

    library, message = capsys.readouterr().out.splitlines()
    assert library.startswith('library: ') and library != 'library: None'
    assert message.startswith('message: ') and message != 'message: None'
    assert ui_languages == ['de']


def test_run_module_writes_the_report_to_a_file(monkeypatch, capsys, tmp_path, ui_languages):
    output = tmp_path / 'report.txt'

    _run_main(monkeypatch, str(output))

    assert capsys.readouterr().out == ''
    assert output.read_text(encoding='utf-8').startswith('library: ')
