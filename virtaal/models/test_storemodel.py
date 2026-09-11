#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.models.storemodel import StoreModel


class _FakeController:
    def compare_stats(self, old, new):
        pass


_OLD_PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Hallo"
'''

_NEW_PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr ""

msgid "World"
msgstr ""
'''


def test_update_file_merges_a_newer_template(tmp_path):
    # Real crash (#3323): update_file() imported statsdb from
    # translate.storage instead of virtaal.support, raising ImportError
    # on any translate-toolkit version without that submodule - then,
    # once that's fixed, os.write() with str(store) instead of a real
    # serialize() raised TypeError, since str.write() needs bytes.
    old_path = tmp_path / "old.po"
    new_path = tmp_path / "new.po"
    old_path.write_bytes(_OLD_PO)
    new_path.write_bytes(_NEW_PO)

    model = StoreModel(str(old_path), _FakeController())
    model.update_file(str(new_path))

    units = {u.source: u.target for u in model.get_units()}
    assert units == {"Hello": "Hallo", "World": ""}
