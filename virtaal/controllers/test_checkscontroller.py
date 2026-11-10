#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
from types import SimpleNamespace

import pytest
from translate.storage import po, qm, ts2

from virtaal.controllers.checkscontroller import ChecksController


class _FakeSignalSource(SimpleNamespace):
    def connect(self, signal, handler):
        return 1


def _make_controller():
    main_controller = _FakeSignalSource(
        store_controller=_FakeSignalSource(get_store=lambda: None),
        unit_controller=_FakeSignalSource(),
        lang_controller=_FakeSignalSource(),
    )
    return ChecksController(main_controller)


def _ts_store(source, target):
    return ts2.tsfile.parsestring(
        b'<?xml version="1.0" encoding="utf-8"?>\n'
        b'<!DOCTYPE TS><TS version="2.0" language="af"><context><name>Main</name>'
        b'<message><source>' + source.encode() + b'</source>'
        b'<translation>' + target.encode() + b'</translation></message>'
        b'</context></TS>')


def test_ts_and_qm_files_default_to_the_qt_checker():
    controller = _make_controller()

    assert controller.default_checker_code(_ts_store('File', 'Lêer')) == 'qt'
    assert controller.default_checker_code(qm.qmfile()) == 'qt'


def test_a_files_own_project_style_wins_over_its_format_default():
    controller = _make_controller()
    store = _ts_store('File', 'Lêer')
    store.setprojectstyle('kde')

    assert controller.default_checker_code(store) == 'kde'


def test_po_files_without_a_project_style_keep_the_default_checker():
    assert _make_controller().default_checker_code(po.pofile()) is None


def test_store_loaded_sets_the_format_default_checker():
    controller = _make_controller()
    codes = []
    controller.set_checker_by_code = codes.append
    store_controller = SimpleNamespace(
        store=SimpleNamespace(_trans_store=_ts_store('File', 'Lêer')),
        cursor=_FakeSignalSource(deref=lambda: None),
    )

    controller._on_store_loaded(store_controller)

    assert codes == ['qt']


@pytest.mark.parametrize(('source', 'target', 'fails'), [
    ('&amp;File', 'Lêer', True),
    ('&amp;File', '&amp;Lêer', False),
    # "&&" is a literal ampersand, not an accelerator
    ('&amp;File', '&amp;&amp;Lêer', True),
    ('Save &amp;&amp; Quit', 'Stoor &amp;&amp; Sluit', False),
    ('&amp;Edit', '_Wysig', True),
])
def test_qt_checker_checks_ampersand_accelerators(source, target, fails):
    checker = _make_controller().checker_info['qt']()
    unit = _ts_store(source, target).units[0]

    assert ('accelerators' in checker.run_filters(unit)) is fails


# Spelling (#4680) #

@pytest.fixture
def flatpak_enchant(monkeypatch):
    """Enchant as in the Flatpak: en_US and en_GB dictionaries, none
    named just en, so enchant.Dict('en') raises."""
    from virtaal.support.enchant_compat import import_enchant

    enchant = import_enchant()
    from translate.filters import spelling
    if enchant is None or not spelling.available:
        pytest.skip("pyenchant is not available")
    tags = ('en_GB', 'en_US')

    class Dict:
        def __init__(self, tag):
            if tag not in tags:
                raise enchant.errors.DictNotFoundError(tag)
            self.tag = tag

        def check(self, word):
            return word != 'Teh'

        def suggest(self, word):
            return []

    monkeypatch.setattr(enchant, 'Dict', Dict)
    monkeypatch.setattr(enchant, 'dict_exists', lambda tag: tag in tags)
    monkeypatch.setattr(enchant, 'list_languages', lambda: list(tags))
    monkeypatch.setattr(spelling, 'checkers', {})
    spelling.simple_check.cache_clear()
    yield
    spelling.simple_check.cache_clear()


def _checks_controller(target_lang):
    controller = _make_controller()
    controller.main_controller.lang_controller.target_lang = SimpleNamespace(code=target_lang)
    controller.main_controller.unit_controller.current_unit = None
    controller._projview = SimpleNamespace(set_checker_name=lambda name: None)
    controller.set_checker_by_code(None)
    return controller


def _checker_for(target_lang):
    return _checks_controller(target_lang).get_checker()


def _unit(source, target):
    unit = po.pounit(source)
    unit.target = target
    return unit


@pytest.mark.parametrize('target_lang', ['en', 'af'])
def test_spelling_check_logs_no_traceback_without_an_exact_dictionary(flatpak_enchant, caplog, target_lang):
    checker = _checker_for(target_lang)

    with caplog.at_level(logging.ERROR):
        checker.run_filters(_unit('Open the file', 'Open the file'))

    assert [r.getMessage() for r in caplog.records if r.name == 'translate.filters.spelling'] == []


def test_spelling_check_uses_the_default_region_for_a_bare_code(flatpak_enchant):
    checker = _checker_for('en')

    failures = checker.run_filters(_unit('The file', 'Teh file'))

    assert 'spellcheck' in failures


def test_a_new_target_language_gets_its_dictionary(flatpak_enchant, caplog):
    controller = _checks_controller('af')

    with caplog.at_level(logging.ERROR):
        controller._on_target_lang_changed(None, 'en')
        failures = controller.get_checker().run_filters(_unit('The file', 'Teh file'))

    assert 'spellcheck' in failures
    assert [r for r in caplog.records if r.name == 'translate.filters.spelling'] == []
