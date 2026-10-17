#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from io import BytesIO

import pytest
from translate.storage import factory, poparser

import virtaal.models.storemodel  # noqa: F401 - installs the patch, as the app does
from virtaal.support import poparser_compat


def _po(charset, target):
    text = (
        'msgid ""\n'
        'msgstr ""\n'
        '"MIME-Version: 1.0\\n"\n'
        f'"Content-Type: text/plain; charset={charset}\\n"\n'
        '"Content-Transfer-Encoding: 8bit\\n"\n'
        '\n'
        'msgid "Save the file"\n'
        f'msgstr "{target}"\n'
    )
    data = BytesIO(text.encode(charset))
    data.name = 'legacy.po'
    return data


@pytest.mark.parametrize('charset, target', [
    ('ISO-8859-1', 'Stoor die lêer'),
    ('KOI8-R', 'Сохранить файл'),
    ('UTF-8', 'Stoor die lêer'),
])
def test_a_po_file_in_its_header_charset_opens(charset, target):
    # #4390: translate-toolkit 3.19.0+ raised UnicodeDecodeError for the
    # legacy charsets.
    store = factory.getobject(_po(charset, target))

    assert store.units[1].target == target


def test_the_patch_is_installed_where_translate_toolkit_needs_it():
    state_class = getattr(poparser, 'PoParseState', None)
    if state_class is None:
        pytest.skip('translate-toolkit before 3.19 has no PoParseState')
    assert state_class.set_encoding.__qualname__.startswith(poparser_compat._patch.__qualname__)
