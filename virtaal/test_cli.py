#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import re
from pathlib import Path

import pytest

from virtaal import cli
from virtaal.common import pan_app


@pytest.fixture(autouse=True)
def _isolate_pan_app_state(monkeypatch):
    # cli.main() reassigns pan_app.settings/DEBUG as a side effect of
    # parsing real argv - snapshot so monkeypatch restores them.
    monkeypatch.setattr(pan_app, 'settings', pan_app.settings)
    monkeypatch.setattr(pan_app, 'DEBUG', pan_app.DEBUG)


def _run_cli(monkeypatch, argv):
    started = []
    monkeypatch.setattr(cli, 'run_virtaal', lambda startup_file: started.append(startup_file))
    monkeypatch.setattr('os._exit', lambda code: None)
    cli.main(argv)
    return started


def test_no_arguments_runs_with_no_startup_file_and_debug_off(monkeypatch):
    started = _run_cli(monkeypatch, ['virtaal'])

    assert started == [None]
    assert pan_app.DEBUG is False


def test_a_positional_argument_is_passed_through_as_the_startup_file(monkeypatch):
    started = _run_cli(monkeypatch, ['virtaal', 'file.po'])

    assert started == ['file.po']


def test_debug_flag_enables_debug_mode(monkeypatch):
    _run_cli(monkeypatch, ['virtaal', '--debug'])

    assert pan_app.DEBUG is True


def test_a_second_positional_argument_is_rejected(monkeypatch):
    monkeypatch.setattr(cli, 'run_virtaal', lambda startup_file: None)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', 'file1.po', 'file2.po'])


def test_config_switches_the_active_settings_file(monkeypatch, tmp_path):
    created = []

    class _FakeSettings:
        def __init__(self, filename):
            created.append(filename)

    monkeypatch.setattr(pan_app, 'Settings', _FakeSettings)
    config_file = tmp_path / 'virtaal.ini'
    config_file.write_text('')

    _run_cli(monkeypatch, ['virtaal', '--config', str(config_file)])

    assert created == [str(config_file)]
    assert isinstance(pan_app.settings, _FakeSettings)


def test_an_unreadable_config_file_is_a_fatal_argument_error(monkeypatch, tmp_path):
    def raises(filename):
        raise OSError('boom')
    monkeypatch.setattr(pan_app, 'Settings', raises)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--config', str(tmp_path / 'missing.ini')])


def test_log_flag_configures_logging_to_stderr(monkeypatch):
    calls = []
    monkeypatch.setattr(logging, 'basicConfig', lambda **kwargs: calls.append(kwargs))

    _run_cli(monkeypatch, ['virtaal', '--log', '-'])

    assert calls[0]['stream'] is not None
    assert calls[0]['level'] == logging.INFO


def test_log_and_debug_together_use_debug_level_and_format(monkeypatch):
    calls = []
    monkeypatch.setattr(logging, 'basicConfig', lambda **kwargs: calls.append(kwargs))

    _run_cli(monkeypatch, ['virtaal', '--log', '-', '--debug'])

    assert calls[0]['level'] == logging.DEBUG
    assert '%(funcName)s' in calls[0]['format']


def test_log_to_a_named_file(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(logging, 'basicConfig', lambda **kwargs: calls.append(kwargs))
    log_file = tmp_path / 'out.log'

    _run_cli(monkeypatch, ['virtaal', '--log', str(log_file)])

    assert calls[0]['filename'] == str(log_file)
    assert calls[0]['filemode'] == 'w'


def test_an_unwritable_log_file_is_a_fatal_argument_error(monkeypatch, tmp_path):
    def raises(**kwargs):
        raise OSError('boom')
    monkeypatch.setattr(logging, 'basicConfig', raises)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--log', str(tmp_path / 'out.log')])


def test_pseudo_translation_and_pseudo_translation_bidi_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(cli, 'run_virtaal', lambda startup_file: None)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--pseudo-translation', '--pseudo-translation-bidi'])


def _stub_pseudo_generator(monkeypatch):
    import importlib.util
    calls = []

    class _FakeSpec:
        loader = type('L', (), {'exec_module': staticmethod(lambda module: None)})()

    def fake_spec_from_file_location(name, path):
        return _FakeSpec()

    def fake_module_from_spec(spec):
        module = type('M', (), {})()
        module.generate_locale = lambda code, localedir=None: calls.append(code)
        return module

    monkeypatch.setattr(importlib.util, 'spec_from_file_location', fake_spec_from_file_location)
    monkeypatch.setattr(importlib.util, 'module_from_spec', fake_module_from_spec)
    return calls


def test_pseudo_translation_regenerates_the_locale_and_switches_to_it(monkeypatch):
    generated = _stub_pseudo_generator(monkeypatch)
    switched = []
    monkeypatch.setattr(pan_app, 'set_ui_language', lambda lang: switched.append(lang))

    _run_cli(monkeypatch, ['virtaal', '--pseudo-translation'])

    assert generated == ['pseudo']
    assert switched == ['pseudo']


def test_pseudo_translation_bidi_also_forces_a_right_to_left_layout(monkeypatch):
    _stub_pseudo_generator(monkeypatch)
    monkeypatch.setattr(pan_app, 'set_ui_language', lambda lang: None)
    from gi.repository import Gtk
    directions = []
    monkeypatch.setattr(Gtk.Widget, 'set_default_direction', staticmethod(lambda d: directions.append(d)))

    _run_cli(monkeypatch, ['virtaal', '--pseudo-translation-bidi'])

    assert directions == [Gtk.TextDirection.RTL]


def test_pseudo_translation_with_no_matching_locale_is_a_fatal_argument_error(monkeypatch):
    _stub_pseudo_generator(monkeypatch)

    def raises(lang):
        raise OSError('no such locale')
    monkeypatch.setattr(pan_app, 'set_ui_language', raises)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--pseudo-translation'])


def test_lang_switches_the_ui_language(monkeypatch):
    switched = []
    monkeypatch.setattr(pan_app, 'set_ui_language', lambda lang: switched.append(lang))

    _run_cli(monkeypatch, ['virtaal', '--lang', 'fr'])

    assert switched == ['fr']


def test_lang_with_no_matching_translation_is_a_fatal_argument_error(monkeypatch):
    def raises(lang):
        raise OSError('no such translation')
    monkeypatch.setattr(pan_app, 'set_ui_language', raises)

    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--lang', 'zz'])


def test_rtl_locale_without_a_translation_is_forced_back_to_ltr(monkeypatch):
    # See issue #1806: GTK decides its own default direction from its
    # own translation for the process locale, independent of whether
    # virtaal itself is translated.
    monkeypatch.setattr(pan_app, 'has_ui_translation', False)
    from gi.repository import Gtk
    monkeypatch.setattr(Gtk, 'get_locale_direction', lambda: Gtk.TextDirection.RTL)
    directions = []
    monkeypatch.setattr(Gtk.Widget, 'set_default_direction', staticmethod(lambda d: directions.append(d)))

    _run_cli(monkeypatch, ['virtaal'])

    assert directions == [Gtk.TextDirection.LTR]


def test_rtl_locale_with_a_real_translation_is_left_alone(monkeypatch):
    monkeypatch.setattr(pan_app, 'has_ui_translation', True)
    from gi.repository import Gtk
    monkeypatch.setattr(Gtk, 'get_locale_direction', lambda: Gtk.TextDirection.RTL)
    directions = []
    monkeypatch.setattr(Gtk.Widget, 'set_default_direction', staticmethod(lambda d: directions.append(d)))

    _run_cli(monkeypatch, ['virtaal'])

    assert directions == []


def test_ltr_default_direction_is_left_alone_regardless_of_translation(monkeypatch):
    monkeypatch.setattr(pan_app, 'has_ui_translation', False)
    from gi.repository import Gtk
    monkeypatch.setattr(Gtk, 'get_locale_direction', lambda: Gtk.TextDirection.LTR)
    directions = []
    monkeypatch.setattr(Gtk.Widget, 'set_default_direction', staticmethod(lambda d: directions.append(d)))

    _run_cli(monkeypatch, ['virtaal'])

    assert directions == []


def test_profile_runs_under_cprofile_and_writes_kcachegrind_output(monkeypatch, tmp_path):
    import devsupport.profiling as profiling

    started = []
    monkeypatch.setattr(cli, 'run_virtaal', lambda startup_file: started.append(startup_file))
    written = []
    monkeypatch.setattr(profiling.KCacheGrind, 'output', lambda self, out_file: written.append(out_file.name))
    profile_file = tmp_path / 'out.profile'

    cli.main(['virtaal', '--profile', str(profile_file), 'file.po'])

    assert started == ['file.po']
    assert written == [str(profile_file)]


def test_profile_with_an_unwritable_path_is_a_fatal_argument_error(monkeypatch):
    with pytest.raises(SystemExit):
        cli.main(['virtaal', '--profile', '/nonexistent-dir/out.profile'])


def test_every_cli_option_is_documented_in_docs_cli_options_rst():
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "cli_options.rst"
    docs_text = docs_path.read_text()

    missing = [
        option
        for action in cli.build_parser()._actions
        for option in action.option_strings
        if not re.search(r'(?<![\w-])' + re.escape(option) + r'(?![\w-])', docs_text)
    ]

    assert not missing, (
        f"bin/virtaal accepts {missing} but docs/cli_options.rst doesn't "
        "mention it - see #3777"
    )
