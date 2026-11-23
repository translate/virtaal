#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import errno
import os

import pytest

from virtaal.common.platform import platform
from virtaal.models.storemodel import StoreModel
from virtaal.support import statsdb, statsworker


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
    # #3808: the merged store from pot2po has no filename or fileobj of
    # its own.
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


@pytest.fixture
def fills(monkeypatch):
    queued = []
    monkeypatch.setattr(statsworker, 'fill_in_background', queued.append)
    return queued


def test_opening_a_file_leaves_the_stats_cache_to_the_worker(tmp_path, monkeypatch, fills):
    path = tmp_path / "old.po"
    path.write_bytes(_OLD_PO)
    monkeypatch.setattr(statsdb, 'StatsCache', lambda *a: pytest.fail('stats cache used on open'))

    model = StoreModel(str(path), _FakeController())

    assert model.stats['translated'] == [0]
    assert fills == [str(path)]


def test_saving_fills_the_stats_cache_for_the_saved_file(tmp_path, monkeypatch, fills):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'write', lambda: None)
    path = tmp_path / "old.po"
    path.write_bytes(_OLD_PO)
    model = StoreModel(str(path), _SavingController('af'))

    model.save_file(str(tmp_path / "saved.po"))

    assert fills == [str(path), str(tmp_path / "saved.po")]


@pytest.fixture
def qm_copy(tmp_path):
    import shutil
    source = os.path.join(os.path.dirname(__file__), '..', '..', 'devsupport', 'testfiles', 'workflow.qm')
    path = tmp_path / 'workflow.qm'
    shutil.copy(source, path)
    return path


def test_saving_a_qm_file_leaves_it_untouched(qm_copy):
    original = qm_copy.read_bytes()
    model = StoreModel(str(qm_copy), _FakeController())

    with pytest.raises(NotImplementedError):
        model.save_file()

    assert qm_copy.read_bytes() == original


def test_saving_a_qm_file_elsewhere_writes_nothing(qm_copy, tmp_path):
    model = StoreModel(str(qm_copy), _FakeController())

    with pytest.raises(NotImplementedError):
        model.save_file(str(tmp_path / 'other.qm'))

    assert not (tmp_path / 'other.qm').exists()


def test_update_file_compares_the_old_stats_with_the_merged_ones(tmp_path):
    old_path = tmp_path / "old.po"
    new_path = tmp_path / "new.po"
    old_path.write_bytes(_OLD_PO)
    new_path.write_bytes(_NEW_PO)
    compared = []
    controller = _FakeController()
    controller.compare_stats = lambda old, new: compared.append(
        {key: (len(old[key]), len(new[key])) for key in ('total', 'translated', 'untranslated')})

    model = StoreModel(str(old_path), controller)
    model.update_file(str(new_path))

    assert compared == [{'total': (1, 2), 'translated': (1, 1), 'untranslated': (0, 1)}]


def test_without_a_file_there_are_no_stats(tmp_path):
    model = StoreModel.__new__(StoreModel)
    model.filename = None
    model._trans_store = None

    assert model.get_stats_totals() == {}
    assert model.update_stats() is None
    assert model.stats is None


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


def test_get_live_stats_totals_matches_the_saved_totals_for_an_unmodified_file(tmp_path):
    model = _states_model(tmp_path)

    assert model.get_live_stats_totals() == model.get_stats_totals()


def test_get_live_stats_totals_counts_unsaved_changes(tmp_path):
    model = _states_model(tmp_path)
    saved = model.get_stats_totals()
    model[2].target = "Maak toe"

    live = model.get_live_stats_totals()

    assert model.get_stats_totals() == saved
    assert 'empty' not in live
    assert live['unreviewed'] == {'units': 2, 'sourcewords': 2, 'targetwords': 3}


_XLIFF = b'''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="x" source-language="en-US" target-language="en-GB" datatype="plaintext"><body>
<trans-unit id="1"><source>Color</source><target>Colour</target></trans-unit>
</body></file></xliff>
'''


def _xliff_model(tmp_path):
    path = tmp_path / "regional.xlf"
    path.write_bytes(_XLIFF)
    return StoreModel(str(path), _FakeController())


def test_a_regional_language_code_is_kept_for_the_same_language(tmp_path):
    # Virtaal knows en-US only as "en"; the file's own code stays.
    model = _xliff_model(tmp_path)

    model.set_source_language("en")
    model.set_target_language("en_GB")

    assert model._trans_store.getsourcelanguage() == "en-US"
    assert model._trans_store.gettargetlanguage() == "en-GB"


def test_a_different_language_replaces_the_files_code(tmp_path):
    model = _xliff_model(tmp_path)

    model.set_source_language("de")
    model.set_target_language("af")

    assert model._trans_store.getsourcelanguage() == "de"
    assert model._trans_store.gettargetlanguage() == "af"


def test_set_language_reports_whether_the_file_changed(tmp_path):
    model = _xliff_model(tmp_path)

    assert model.set_source_language("de") is True
    assert model.set_source_language("de") is False
    assert model.set_target_language("af") is True
    assert model.set_target_language("af") is False


class _SavingController(_FakeController):
    def __init__(self, target_lang):
        from types import SimpleNamespace

        from virtaal.models.langmodel import LanguageModel
        self.main_controller = SimpleNamespace(
            get_translator_details=lambda: (None, None, None),
            lang_controller=SimpleNamespace(target_lang=LanguageModel(target_lang)),
            checks_controller=SimpleNamespace(code=None))


def _save_po(tmp_path, monkeypatch, header, target_lang):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'write', lambda: None)
    path = tmp_path / "header.po"
    path.write_bytes(b'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
                     + header + b'\nmsgid "Hello"\nmsgstr "Hallo"\n')
    model = StoreModel(str(path), _SavingController(target_lang))
    model.save_file()
    return StoreModel(str(path), _FakeController())._trans_store.parseheader()


def test_saving_keeps_a_regional_language_header(tmp_path, monkeypatch):
    header = _save_po(tmp_path, monkeypatch, b'"Language: de_CH\\n"\n', "de")

    assert header["Language"] == "de_CH"


def test_saving_adds_a_missing_language_header(tmp_path, monkeypatch):
    header = _save_po(tmp_path, monkeypatch, b'', "de")

    assert header["Language"] == "de"


def test_saving_keeps_each_targets_normalisation_form(tmp_path, monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'write', lambda: None)
    path = tmp_path / "forms.po"
    path.write_text('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
                    'msgid "Coffee"\nmsgstr "Café"\n\n'
                    'msgid "Vietnamese"\nmsgstr "Tiếng Việt"\n\n'
                    'msgid "Korean"\nmsgstr ""\n', encoding="utf-8")
    model = StoreModel(str(path), _SavingController("de"))
    model.get_units()[2].target = '한'  # NFD 한

    model.save_file()

    saved = [u.target for u in StoreModel(str(path), _FakeController()).get_units()]
    assert saved == ['Café', 'Tiếng Việt', '한']


# Slovenian with Virtaal's form count (4) but a different form order.
_SL_PLURAL_FORMS = "nplurals=4; plural=(n%100==1 ? 1 : n%100==2 ? 2 : n%100==3 || n%100==4 ? 3 : 0);"


def test_saving_keeps_the_files_plural_forms_for_the_same_number_of_forms(tmp_path, monkeypatch):
    header = _save_po(tmp_path, monkeypatch,
                      b'"Language: sl\\n"\n"Plural-Forms: ' + _SL_PLURAL_FORMS.encode() + b'\\n"\n', "sl")

    assert header["Plural-Forms"] == _SL_PLURAL_FORMS


# GNOME's Ukrainian, one form more than translate-toolkit's (#3197).
_UK_PLURAL_FORMS = ("nplurals=4; plural=n==1 ? 3 : n%10==1 && n%100!=11 ? 0 : "
                    "n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2;")
_UK_HEADER = b'"Plural-Forms: ' + _UK_PLURAL_FORMS.encode() + b'\\n"\n'


def test_saving_keeps_the_files_plural_forms_for_a_different_number_of_forms(tmp_path, monkeypatch):
    header = _save_po(tmp_path, monkeypatch, b'"Language: uk\\n"\n' + _UK_HEADER, "uk")

    assert header["Plural-Forms"] == _UK_PLURAL_FORMS


def test_saving_adds_missing_plural_forms(tmp_path, monkeypatch):
    header = _save_po(tmp_path, monkeypatch, b'', "pt_BR")

    assert header["Plural-Forms"] == "nplurals=2; plural=(n > 1);"


@pytest.fixture(params=[
    (2, '('),                          # not an equation
    (2, 'n'),                          # forms 2 and up: msgfmt rejects the file
    (3, '(n != 1)'),                   # form 2 never used
    (0, '0'),
])
def invalid_plural_language(request):
    # #4351: Add Missing Language takes any plural equation.
    from virtaal.models.langmodel import LanguageModel
    LanguageModel.languages['xx'] = ('Xx',) + request.param
    yield 'xx'
    LanguageModel.languages.pop('xx', None)


def test_every_shipped_plural_equation_is_usable():
    from virtaal.models.langmodel import LanguageModel
    from virtaal.models.storemodel import _usable_plural
    LanguageModel('af')  # LanguageModel.languages populates on first use
    rules = [(code, n, p) for code, (_name, n, p) in LanguageModel.languages.items() if p]

    assert rules
    assert [code for code, n, p in rules if not _usable_plural(n, p)] == []


def test_saving_leaves_out_an_invalid_plural_equation(tmp_path, monkeypatch, invalid_plural_language):
    header = _save_po(tmp_path, monkeypatch, b'', invalid_plural_language)

    assert "Plural-Forms" not in header
    assert header["Language"] == invalid_plural_language


def test_changing_language_leaves_out_an_invalid_plural_equation(tmp_path, invalid_plural_language):
    path = tmp_path / "de.po"
    path.write_bytes(b'msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
                     b'\nmsgid "Hello"\nmsgstr "Hallo"\n')
    model = StoreModel(str(path), _FakeController())

    model.set_target_language(invalid_plural_language)

    assert model._trans_store.getheaderplural() == ("2", "(n != 1)")


def test_changing_language_writes_the_new_languages_plural_forms(tmp_path):
    path = tmp_path / "de.po"
    path.write_bytes(b'msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
                     b'\nmsgid "Hello"\nmsgstr "Hallo"\n')
    model = StoreModel(str(path), _FakeController())

    model.set_target_language("fr")

    assert model._trans_store.getheaderplural() == ("2", "(n > 1)")


def test_changing_language_updates_the_plural_count(tmp_path):
    path = tmp_path / "de.po"
    path.write_bytes(b'msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
                     b'\nmsgid "Hello"\nmsgstr "Hallo"\n')
    model = StoreModel(str(path), _FakeController())

    model.set_target_language("sl")

    assert model.get_declared_nplurals() == 4


def test_setting_the_language_keeps_plural_forms_declared_without_one(tmp_path):
    path = tmp_path / "uk.po"
    path.write_bytes(b'msgid ""\nmsgstr ""\n' + _UK_HEADER + b'\nmsgid "Hello"\nmsgstr "Pryvit"\n')
    model = StoreModel(str(path), _FakeController())

    assert model.set_target_language("uk") is True

    assert model._trans_store.parseheader()["Plural-Forms"] == _UK_PLURAL_FORMS
    assert model.get_declared_nplurals() == 4


def test_declared_nplurals_ignores_a_templates_placeholder(tmp_path):
    path = tmp_path / "template.pot"
    path.write_bytes(b'msgid ""\nmsgstr ""\n"Plural-Forms: nplurals=INTEGER; plural=EXPRESSION;\\n"\n'
                     b'\nmsgid "Hello"\nmsgstr ""\n')

    assert StoreModel(str(path), _FakeController()).get_declared_nplurals() is None


_CHECKS_PO = """msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Open the file."
msgstr "Maak die l\u00eaer oop"

msgid "Close"
msgstr "Maak toe"
"""


def _checks_model(tmp_path):
    path = tmp_path / "checks.po"
    path.write_text(_CHECKS_PO, encoding="utf-8")
    model = StoreModel(str(path), _FakeController())
    model._update_header = lambda ask=True: None
    return model


def test_update_checks_includes_unsaved_edits(tmp_path):
    # The stats cache is keyed on the file on disk (#3988).
    from translate.filters import checks
    model = _checks_model(tmp_path)
    assert model.update_checks(checker=checks.StandardChecker()) == {'check-endpunc': [0]}
    model[0].target = "Maak die l\u00eaer oop."
    model[1].target = "Maak toe."
    model.update_unit_checks(0)
    model.update_unit_checks(1)

    assert model.update_checks() == {'check-endpunc': [1]}


def test_update_unit_checks_moves_a_unit_between_failing_checks(tmp_path):
    from translate.filters import checks
    model = _checks_model(tmp_path)
    model.update_checks(checker=checks.StandardChecker())

    model[0].target = "Maak die l\u00eaer oop."
    assert model.update_unit_checks(0) is True
    assert model.checks == {}

    model[1].target = "Maak toe."
    assert model.update_unit_checks(1) is True
    assert model.checks == {'check-endpunc': [1]}


def test_update_unit_checks_reports_no_change_for_the_same_failures(tmp_path):
    from translate.filters import checks
    model = _checks_model(tmp_path)
    model.update_checks(checker=checks.StandardChecker())

    assert model.update_unit_checks(0) is False
    assert model.checks == {'check-endpunc': [0]}


def test_update_unit_checks_before_any_checks_only_marks_the_unit(tmp_path):
    model = _checks_model(tmp_path)

    assert model.update_unit_checks(0) is False
    assert model.checks is None


def test_save_file_forgets_the_edited_units(tmp_path):
    from translate.filters import checks
    model = _checks_model(tmp_path)
    model.update_checks(checker=checks.StandardChecker())
    model[0].target = "Maak die l\u00eaer oop."
    model.update_unit_checks(0)

    model.save_file()

    assert model._edited_units == set()
    assert model.update_checks() == {}


def test_write_copy_writes_the_edits_and_leaves_the_file_alone(tmp_path):
    import io
    model = _checks_model(tmp_path)
    before = (tmp_path / "checks.po").read_bytes()
    model[0].target = "Maak die l\u00eaer oop."
    copy = io.BytesIO()

    model.write_copy(copy)

    assert "Maak die l\u00eaer oop." in copy.getvalue().decode("utf-8")
    assert (tmp_path / "checks.po").read_bytes() == before
    assert model.filename == str(tmp_path / "checks.po")


def test_write_copy_updates_the_copys_header_without_asking(tmp_path, monkeypatch):
    import io

    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'write', lambda: pytest.fail("settings written"))
    monkeypatch.setitem(pan_app.settings.translator, 'name', 'Ann Vertaler')
    monkeypatch.setitem(pan_app.settings.translator, 'email', 'ann@example.org')
    monkeypatch.setitem(pan_app.settings.translator, 'team', '')
    path = tmp_path / "copy.po"
    path.write_bytes(_STATES_PO)
    before = path.read_bytes()
    controller = _SavingController("af")
    controller.main_controller.get_translator_details = lambda: pytest.fail("asked for details")
    controller.main_controller.checks_controller.code = "openoffice"
    copy = io.BytesIO()

    StoreModel(str(path), controller).write_copy(copy)

    copy_path = tmp_path / "copied.po"
    copy_path.write_bytes(copy.getvalue())
    header = StoreModel(str(copy_path), _FakeController())._trans_store.parseheader()
    assert header["Last-Translator"] == "Ann Vertaler <ann@example.org>"
    assert header["X-Project-Style"] == "openoffice"
    assert header["Language"] == "af"
    assert "PO-Revision-Date" in header
    assert path.read_bytes() == before


def test_update_unit_checks_uses_failures_it_is_given(tmp_path):
    from translate.filters import checks
    model = _checks_model(tmp_path)
    model.update_checks(checker=checks.StandardChecker())

    assert model.update_unit_checks(1, {'printf': 'msg'}) is True
    assert model.checks == {'check-endpunc': [0], 'check-printf': [1]}


def test_len_is_zero_without_a_store():
    model = StoreModel.__new__(StoreModel)
    model._trans_store = None

    assert len(model) == 0


# The tutorial is deleted from disk as soon as it is open (#4312).

def test_update_checks_for_a_file_no_longer_on_disk(tmp_path):
    from translate.filters import checks
    model = _checks_model(tmp_path)
    (tmp_path / "checks.po").unlink()

    assert model.update_checks(checker=checks.StandardChecker()) == {'check-endpunc': [0]}


def test_get_stats_totals_for_a_file_no_longer_on_disk(tmp_path):
    model = _states_model(tmp_path)
    (tmp_path / "states.po").unlink()

    assert model.get_stats_totals() == model.get_live_stats_totals()


def test_update_file_for_a_file_no_longer_on_disk(tmp_path):
    old_path = tmp_path / "old.po"
    new_path = tmp_path / "new.po"
    old_path.write_bytes(_OLD_PO)
    new_path.write_bytes(_NEW_PO)
    compared = []
    controller = _FakeController()
    controller.compare_stats = lambda old, new: compared.append(
        {key: (len(old[key]), len(new[key])) for key in ('total', 'translated', 'untranslated')})
    model = StoreModel(str(old_path), controller)
    old_path.unlink()

    model.update_file(str(new_path))

    assert compared == [{'total': (1, 2), 'translated': (1, 1), 'untranslated': (0, 1)}]


_OPEN_XLIFF = b"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original="x" source-language="en" target-language="af" datatype="po"><body>
<trans-unit id="1"><source>Hello</source><target>Hallo</target></trans-unit>
</body></file></xliff>
"""

_OPEN_TS = b"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="af"><context><name>c</name>
<message><source>Hello</source><translation>Hallo</translation></message>
</context></TS>
"""

_OPEN_FTL = b"Hello = Hallo\n"


@pytest.mark.parametrize("name, content", [
    ("old.xlf", _OPEN_XLIFF),
    ("old.ts", _OPEN_TS),
    # pot2po "succeeds" here, but hands back a PO store that would then be
    # saved over the .ftl file.
    ("old.ftl", _OPEN_FTL),
], ids=["xliff", "ts", "fluent"])
def test_update_file_refuses_a_non_po_file_and_keeps_it(tmp_path, name, content):
    old_path = tmp_path / name
    new_path = tmp_path / "new.pot"
    old_path.write_bytes(content)
    new_path.write_bytes(_NEW_PO)
    model = StoreModel(str(old_path), _FakeController())
    trans_store = model._trans_store

    assert not model.can_update_from_template
    with pytest.raises(ValueError):
        model.update_file(str(new_path))

    assert model._trans_store is trans_store
    assert [u.target for u in model.get_units()] == ["Hallo"]
    assert old_path.read_bytes() == content


def test_a_failed_update_leaves_the_po_file_as_it_was(tmp_path):
    old_path = tmp_path / "old.po"
    new_path = tmp_path / "new.pot"
    old_path.write_bytes(_OLD_PO)
    new_path.write_bytes(_NEW_PO)
    controller = _FakeController()

    def fail(old, new):
        raise RuntimeError('notice failed')
    controller.compare_stats = fail
    model = StoreModel(str(old_path), controller)
    trans_store, stats, nplurals = model._trans_store, model.stats, model.nplurals

    with pytest.raises(RuntimeError):
        model.update_file(str(new_path))

    assert model._trans_store is trans_store
    assert model.stats == stats
    assert model.nplurals == nplurals
    assert model._edited_units == set()
    assert [u.source for u in model.get_units()] == ["Hello"]


def test_a_po_file_can_be_updated_from_a_template(tmp_path):
    path = tmp_path / "old.po"
    path.write_bytes(_OLD_PO)

    assert StoreModel(str(path), _FakeController()).can_update_from_template


_GERMAN_SOURCE_XLIFF = b'''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
<file original="test" source-language="de" target-language="af" datatype="plaintext"><body>
<trans-unit id="1"><source>Offnen</source></trans-unit>
</body></file></xliff>
'''


def test_the_source_language_comes_from_the_files_first_unit(tmp_path):
    path = tmp_path / "german.xlf"
    path.write_bytes(_GERMAN_SOURCE_XLIFF)

    model = StoreModel(str(path), _FakeController())

    assert model.get_source_language() == "de"


def test_the_store_type_is_the_formats_name(tmp_path):
    assert _states_model(tmp_path).get_store_type() == "Gettext PO file"


def test_a_file_object_without_a_name_loads_as_a_project_file():
    # A file opened from inside a project bundle.
    from io import BytesIO

    model = StoreModel(BytesIO(_STATES_PO), _FakeController())

    assert model.filename == '<projectfile>'
    assert [unit.source for unit in model.get_units()] == ['Open', 'Save', 'Close']


def test_a_file_object_names_itself_with_its_filename():
    from io import BytesIO

    class Named(BytesIO):
        filename = 'states.po'

    model = StoreModel(Named(_STATES_PO), _FakeController())

    assert model.filename == 'states.po'


def test_without_stats_a_unit_changes_no_state_lists(tmp_path):
    model = _states_model(tmp_path)
    model.stats = None

    assert model.update_unit_stats(0) is False


def test_without_a_file_there_are_no_checks():
    model = StoreModel.__new__(StoreModel)
    model._trans_store = None

    model.update_checks()

    assert model.checks is None


def test_saving_records_the_projects_checks_style(tmp_path, monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app.settings, 'write', lambda: None)
    path = tmp_path / "style.po"
    path.write_bytes(_STATES_PO)
    controller = _SavingController("af")
    controller.main_controller.checks_controller.code = "openoffice"

    StoreModel(str(path), controller).save_file()

    header = StoreModel(str(path), _FakeController())._trans_store.parseheader()
    assert header["X-Project-Style"] == "openoffice"


def test_a_format_that_cannot_be_probed_is_assumed_writable(qm_copy):
    class _NeedsAnArgument:
        def __init__(self, required):
            pass

    model = StoreModel(str(qm_copy), _FakeController())
    model._trans_store = _NeedsAnArgument(None)

    model._check_writable()  # must not raise


# Saving goes through a temporary file that replaces the original (#4841).

def _saved_model(tmp_path):
    model = _checks_model(tmp_path)
    model[0].target = "Maak die lêer oop."
    return model, tmp_path / "checks.po"


def _leftovers(folder):
    return sorted(p.name for p in folder.iterdir() if 'virtaal-save' in p.name)


def test_save_file_leaves_the_file_whole_when_serialising_fails(tmp_path, monkeypatch):
    model, path = _saved_model(tmp_path)
    original = path.read_bytes()

    def broken(out):
        out.write(b'msgid ""\n')
        raise ValueError("can't serialise")

    monkeypatch.setattr(model._trans_store, 'serialize', broken)
    with pytest.raises(ValueError):
        model.save_file()

    assert path.read_bytes() == original
    assert _leftovers(tmp_path) == []


def test_save_file_leaves_the_file_whole_when_the_disk_is_full(tmp_path, monkeypatch):
    model, path = _saved_model(tmp_path)
    original = path.read_bytes()

    def full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr('os.fsync', full)
    with pytest.raises(OSError):
        model.save_file()

    assert path.read_bytes() == original
    assert _leftovers(tmp_path) == []


def test_save_file_writes_the_file_and_can_save_again(tmp_path):
    model, path = _saved_model(tmp_path)

    model.save_file()
    assert "Maak die lêer oop." in path.read_text(encoding="utf-8")
    model[1].target = "Maak toe."
    model.save_file()

    assert "Maak toe." in path.read_text(encoding="utf-8")
    assert model.get_filename() == str(path)
    assert _leftovers(tmp_path) == []


def test_save_file_as_writes_the_new_file(tmp_path):
    model, path = _saved_model(tmp_path)
    copy = tmp_path / "copy.po"

    model.save_file(str(copy))

    assert "Maak die lêer oop." in copy.read_text(encoding="utf-8")
    assert "Maak die lêer oop." not in path.read_text(encoding="utf-8")
    assert model.filename == model.get_filename() == str(copy)


@pytest.mark.skipif(platform.is_windows, reason="POSIX modes")
@pytest.mark.parametrize('mode', [0o644, 0o600, 0o664])
def test_save_file_keeps_the_mode(tmp_path, mode):
    model, path = _saved_model(tmp_path)
    os.chmod(path, mode)

    model.save_file()

    assert os.stat(path).st_mode & 0o7777 == mode


@pytest.mark.skipif(platform.is_windows, reason="POSIX modes")
def test_save_file_as_gives_a_new_file_the_usual_mode(tmp_path):
    model, _path = _saved_model(tmp_path)
    old = os.umask(0o022)
    try:
        model.save_file(str(tmp_path / "copy.po"))
    finally:
        os.umask(old)

    assert os.stat(tmp_path / "copy.po").st_mode & 0o777 == 0o644


@pytest.mark.skipif(platform.is_windows, reason="symlinks need privileges on Windows")
def test_save_file_through_a_symlink_keeps_the_link(tmp_path):
    model_dir = tmp_path / "real"
    model_dir.mkdir()
    model, path = _saved_model(model_dir)
    link = tmp_path / "link.po"
    link.symlink_to(path)
    model.save_file(str(link))

    assert link.is_symlink()
    assert os.readlink(link) == str(path)
    assert "Maak die lêer oop." in path.read_text(encoding="utf-8")
    assert _leftovers(model_dir) == [] and _leftovers(tmp_path) == []


def test_save_file_keeps_hard_links(tmp_path):
    model, path = _saved_model(tmp_path)
    other = tmp_path / "other.po"
    os.link(path, other)

    model.save_file()

    assert "Maak die lêer oop." in other.read_text(encoding="utf-8")
    assert os.path.samefile(path, other)


@pytest.mark.parametrize('error', [
    PermissionError(13, "Access is denied"),  # Windows: another program has it open
    OSError(errno.EBUSY, "Device or resource busy"),  # a bind-mounted file
])
def test_save_file_writes_in_place_when_the_file_cant_be_replaced(tmp_path, monkeypatch, error):
    model, path = _saved_model(tmp_path)

    def refused(src, dst):
        raise error

    monkeypatch.setattr('os.replace', refused)
    model.save_file()

    assert "Maak die lêer oop." in path.read_text(encoding="utf-8")
    assert _leftovers(tmp_path) == []


def test_save_file_writes_in_place_when_no_file_can_be_made_beside_it(tmp_path, monkeypatch):
    from virtaal.support import storesave
    model, path = _saved_model(tmp_path)
    original = path.read_bytes()

    def refused(target, mode):
        raise PermissionError(13, "Permission denied", target)

    monkeypatch.setattr(storesave, '_open_temp', refused)
    model.save_file()
    assert "Maak die lêer oop." in path.read_text(encoding="utf-8")

    path.write_bytes(original)
    monkeypatch.setattr(model._trans_store, 'serialize', lambda out: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        model.save_file()
    assert path.read_bytes() == original


@pytest.mark.skipif(platform.is_windows or os.geteuid() == 0,
                    reason="POSIX write permission; root can write anything")
def test_save_file_refuses_a_read_only_file(tmp_path):
    model, path = _saved_model(tmp_path)
    original = path.read_bytes()
    os.chmod(path, 0o444)

    with pytest.raises(PermissionError):
        model.save_file()

    assert path.read_bytes() == original
    assert _leftovers(tmp_path) == []


@pytest.mark.skipif(platform.is_windows, reason="POSIX modes")
def test_save_file_makes_the_temporary_file_owner_only(tmp_path, monkeypatch):
    from virtaal.support import storesave
    model, path = _saved_model(tmp_path)
    os.chmod(path, 0o600)
    modes = []

    def serialize(out, real=model._trans_store.serialize):
        modes.append(os.stat(out.name).st_mode & 0o777)
        real(out)

    def chmod(*args):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(model._trans_store, 'serialize', serialize)
    # Some file systems refuse mode changes.
    monkeypatch.setattr(storesave.os, 'chmod', chmod)
    model.save_file()

    assert modes == [0o600]
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_save_file_without_a_filename_doesnt_write_one(tmp_path, monkeypatch):
    import io

    model = StoreModel(io.BytesIO(_CHECKS_PO.encode("utf-8")), _FakeController())
    model._update_header = lambda: None
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        model.save_file()

    assert list(tmp_path.iterdir()) == []
