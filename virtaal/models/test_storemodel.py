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


def test_update_file_then_save_writes_back_to_the_original_path(tmp_path):
    # Real bug (#3808): the tempfile-based stats hack left .fileobj bound
    # to its own removed tempfile, so save() wrote to a stale path
    # instead of old_path.
    old_path = tmp_path / "old.po"
    new_path = tmp_path / "new.po"
    old_path.write_bytes(_OLD_PO)
    new_path.write_bytes(_NEW_PO)

    model = StoreModel(str(old_path), _FakeController())
    model.update_file(str(new_path))
    model._trans_store.save()

    with open(old_path, "rb") as f:
        saved = f.read()
    assert b"World" in saved
    assert set(tmp_path.iterdir()) == {old_path, new_path}


_STATES_PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Open"
msgstr "Oop"

#, fuzzy
msgid "Save"
msgstr "Stoor"

msgid "Close"
msgstr ""
'''


def _states_model(tmp_path):
    path = tmp_path / "states.po"
    path.write_bytes(_STATES_PO)
    return StoreModel(str(path), _FakeController())


def _recount(model, tmp_path):
    """The stats a fresh load of the model's current units gives."""
    path = tmp_path / "recount.po"
    model._trans_store.savefile(str(path))
    return StoreModel(str(path), _FakeController()).stats


def _copy(stats):
    return {key: (dict((k, list(v)) for k, v in value.items()) if key == 'extended' else list(value))
            for key, value in stats.items()}


def test_update_unit_stats_matches_a_full_recount_after_a_state_change(tmp_path):
    model = _states_model(tmp_path)
    model[1].markfuzzy(False)

    assert model.update_unit_stats(1) is True

    assert model.stats == _recount(model, tmp_path)
    live = model.stats
    assert live['fuzzy'] == []


def test_update_unit_stats_reports_no_change_when_the_state_is_unchanged(tmp_path):
    model = _states_model(tmp_path)
    before = _copy(model.stats)

    assert model.update_unit_stats(0) is False
    assert model.stats == before


def test_update_unit_stats_adds_a_state_no_unit_was_in(tmp_path):
    model = _states_model(tmp_path)
    model[0].markfuzzy(True)

    model.update_unit_stats(0)
    live = model.stats

    assert live == _recount(model, tmp_path)
    assert live['fuzzy'] == [0, 1]
