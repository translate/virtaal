#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from codecs import BOM_UTF8
from io import BytesIO

from translate.storage import factory

import virtaal.models.storemodel  # noqa: F401 - installs the patch, as the app does

FTL = 'workflow.ftl'


def _store(data):
    data = BytesIO(data)
    data.name = 'with-bom.ftl'
    return factory.getobject(data)


def test_a_fluent_file_with_a_byte_order_mark_opens_like_one_without():
    # #4413: Windows editors such as Notepad save a BOM.
    with open('devsupport/testfiles/' + FTL, 'rb') as f:
        data = f.read()

    with_bom = _store(BOM_UTF8 + data)
    without = _store(data)

    assert [u.source for u in with_bom.units] == [u.source for u in without.units]
    assert with_bom.units
