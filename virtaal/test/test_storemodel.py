#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from test_scaffolding import TestScaffolding

from virtaal.models.storemodel import StoreModel


class TestStoreModel(TestScaffolding):
    def test_load(self):
        self.model = StoreModel(self.testfile[1], None) # We can pass "None" as the controller, because it does not have an effect on this test
        self.model.load_file(self.testfile[1])
        assert len(self.model) <= len(self.trans_store.units)
        assert self.model.get_filename() == self.testfile[1]


def test_compute_nplurals_infers_from_data_when_the_format_has_no_declaration():
    # .qm has no working plural-count declaration to read (translate-
    # toolkit's own NumerusRules section reader is unimplemented) -
    # translate/virtaal#1501.
    from translate.storage import factory
    store = factory.getobject('devsupport/testfiles/workflow.qm')
    assert StoreModel._compute_nplurals(None, store) == 2


def test_compute_nplurals_none_without_any_plural_data():
    from translate.storage import mo
    store = mo.mofile()
    assert StoreModel._compute_nplurals(None, store) is None


def _model_with_translator_info(tmp_path, name, email):
    path = tmp_path / "test.po"
    path.write_text('msgid ""\nmsgstr ""\n\nmsgid "Hello"\nmsgstr "Bonjour"\n')

    model = StoreModel(str(path), controller=None)
    model.controller = SimpleNamespace(
        main_controller=SimpleNamespace(
            get_translator_name=lambda: name,
            get_translator_email=lambda: email,
            get_translator_team=lambda: None,
            lang_controller=SimpleNamespace(
                target_lang=SimpleNamespace(code='fr', plural=None, nplurals=None)),
            checks_controller=SimpleNamespace(code=None),
        ))
    return model, path


def test_save_proceeds_when_translator_info_prompts_are_cancelled(tmp_path):
    """Cancelling the translator name/e-mail/team prompt during save
    used to abort the whole save (#1931) - the translated content must
    still be written."""
    model, path = _model_with_translator_info(tmp_path, name=None, email=None)

    model.save_file()  # must not raise

    assert 'msgstr "Bonjour"' in path.read_text()


def test_last_translator_left_as_the_standard_placeholder_when_both_are_missing(tmp_path):
    # Not touching it leaves gettext's own standard unfilled-in
    # placeholder in place, rather than any custom malformed string.
    model, path = _model_with_translator_info(tmp_path, name=None, email=None)
    model.save_file()
    assert 'Last-Translator: FULL NAME <EMAIL@ADDRESS>' in path.read_text()


def test_last_translator_is_bare_name_when_email_is_missing(tmp_path):
    # A cancelled e-mail prompt used to produce "Name <>" (#1931 follow-up).
    model, path = _model_with_translator_info(tmp_path, name="Jan Alleman", email=None)
    model.save_file()
    assert 'Last-Translator: Jan Alleman\\n' in path.read_text()


def test_last_translator_left_as_the_standard_placeholder_when_name_is_missing(tmp_path):
    # A cancelled name prompt used to produce " <email>" (#1931 follow-up) -
    # updatecontributor() itself treats name as required, email as
    # optional, so an email with no name isn't a valid credit either;
    # leaving it untouched keeps gettext's own standard placeholder.
    model, path = _model_with_translator_info(tmp_path, name=None, email="me@example.com")
    model.save_file()
    assert 'Last-Translator: FULL NAME <EMAIL@ADDRESS>' in path.read_text()


def test_last_translator_is_name_and_email_when_both_are_given(tmp_path):
    model, path = _model_with_translator_info(tmp_path, name="Jan Alleman", email="me@example.com")
    model.save_file()
    assert 'Last-Translator: Jan Alleman <me@example.com>\\n' in path.read_text()
