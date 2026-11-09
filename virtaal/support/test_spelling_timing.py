#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import re

import pytest

from virtaal.support import spelling_timing
from virtaal.support.enchant_compat import import_enchant


def _can_check(lang):
    enchant = import_enchant()
    if enchant is None or not enchant.dict_exists(lang):
        return False
    try:
        import gi
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def test_timings_report_each_paste():
    if not _can_check('en_US'):
        pytest.skip("needs GtkSpell and an en_US dictionary")

    report = spelling_timing.timings('en_US', sizes=(300,))

    assert report.splitlines()[0] == 'plugin: checking'
    assert re.search(r'^typing: longest keystroke [0-9.]+ s, 1 marked$', report, re.M)
    marked = re.search(r'^plugin 300: insert [0-9.]+ s, idle [0-9.]+ s, (\d+) marked$', report, re.M)
    assert marked and int(marked.group(1)) > 0
    assert re.search(r'^gtkspell 300: insert [0-9.]+ s, idle [0-9.]+ s, %s marked$' % marked.group(1), report, re.M)
