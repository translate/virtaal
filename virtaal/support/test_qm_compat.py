#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage import factory

from virtaal.support import qm_compat  # noqa: F401 - applies its patch on import


def test_qm_unit_hasplural_true_for_a_real_plural():
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    plural_unit = next(u for u in store.units if u.source.startswith('%n'))
    assert plural_unit.hasplural() is True


def test_qm_unit_hasplural_false_for_a_plain_string():
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    plain_unit = next(u for u in store.units if u.source == 'Open')
    assert plain_unit.hasplural() is False
