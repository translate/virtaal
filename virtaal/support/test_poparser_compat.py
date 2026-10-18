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


@pytest.mark.parametrize('charset', ['UTF-16', 'UTF-32', 'utf-16le'])
def test_a_utf8_file_whose_header_names_a_non_ascii_charset_opens_and_saves_as_utf8(charset):
    # #4409: the header is wrong - a PO file is read as ASCII-compatible
    # lines - so the file is read and written back as UTF-8.
    data = _po(charset, 'Stoor die lêer')
    data = BytesIO(data.getvalue().decode(charset).encode('utf-8'))
    data.name = 'wrong-header.po'

    store = factory.getobject(data)

    assert store.units[1].target == 'Stoor die lêer'
    saved = bytes(store).decode('utf-8')
    assert 'charset=UTF-8' in saved


def test_rescue_charset_leaves_real_utf16_and_unknown_charsets_alone():
    real_utf16 = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-16\\n"\n'.encode('utf-16')
    unknown = b'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=NO-SUCH\\n"\n'

    assert poparser_compat._rescue_charset(real_utf16) == real_utf16
    assert poparser_compat._rescue_charset(unknown) == unknown
