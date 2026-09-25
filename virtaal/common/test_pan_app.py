#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os
from types import SimpleNamespace

import pytest

from virtaal.common import pan_app
from virtaal.common.pan_app import (
    _build_launch_marker,
    _open_frozen_log,
    _read_ini_recovering,
    _set_enchant_env_vars,
    _trim_log_to_last_launches,
    get_config_dir,
)


def test_build_launch_marker_includes_version(monkeypatch):
    monkeypatch.setattr(pan_app, 'version_string', lambda: '1.0.0-beta1 (5bb637f)')
    marker = _build_launch_marker('2026-09-07 22:00:00')
    assert marker == '=== launch 2026-09-07 22:00:00 | Virtaal 1.0.0-beta1 (5bb637f) ===\n'


def test_set_enchant_env_vars_points_at_bundled_dylib(monkeypatch):
    # _set_enchant_env_vars() writes os.environ directly (setdefault, not
    # monkeypatch) - real spellchecker-using tests elsewhere in the suite
    # would pick up these bogus paths for the rest of the process if left
    # behind, so this can't rely on monkeypatch's own auto-cleanup alone.
    for key in ('PYENCHANT_LIBRARY_PATH', 'ENCHANT_MODULE_DIR', 'ENCHANT_DATA_DIR'):
        monkeypatch.delenv(key, raising=False)
    enchant_dir = os.path.join('Some', 'App.app', 'Contents', 'Resources', 'enchant_intel')
    try:
        _set_enchant_env_vars(enchant_dir)
        assert os.environ['PYENCHANT_LIBRARY_PATH'] == \
            os.path.join(enchant_dir, 'lib', 'libenchant.1.dylib')
        assert os.environ['ENCHANT_MODULE_DIR'] == \
            os.path.join(enchant_dir, 'lib', 'enchant')
        assert os.environ['ENCHANT_DATA_DIR'] == \
            os.path.join(enchant_dir, 'share', 'enchant')
    finally:
        for key in ('PYENCHANT_LIBRARY_PATH', 'ENCHANT_MODULE_DIR', 'ENCHANT_DATA_DIR'):
            os.environ.pop(key, None)


def test_open_frozen_log_survives_characters_a_locale_codepage_cant(tmp_path):
    """Real Windows crash: the frozen build's stdout/stderr log used to
    open with no explicit encoding, defaulting to the system locale's
    codepage (e.g. cp1252) - logging.debug() writing a check-failure
    message containing "≠" (U+2260) raised UnicodeEncodeError from
    inside the logging call itself."""
    message = "Different capitalization ≠ expected\n"

    # Confirm this is a real failure mode, not a hypothetical one - the
    # exact codepage the original crash's own traceback named.
    with pytest.raises(UnicodeEncodeError):
        message.encode('cp1252')

    path = str(tmp_path / "test.log")
    f = _open_frozen_log(path)
    try:
        f.write(message)
    finally:
        f.close()

    with open(path, encoding='utf-8') as f:
        assert message in f.read()


def _launch(n):
    return '=== launch 2026-09-%02d 00:00:00 | Virtaal 1.0.0-beta1 (abc%04d) ===\ncontent %d\n' % (n, n, n)


def test_trim_log_to_last_launches_keeps_only_the_tail(tmp_path):
    path = str(tmp_path / "test.log")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(_launch(n) for n in range(1, 6)))

    _trim_log_to_last_launches(path, keep=2)

    with open(path, encoding='utf-8') as f:
        kept = f.read()
    assert kept == _launch(4) + _launch(5)


def test_trim_log_to_last_launches_leaves_a_short_log_alone(tmp_path):
    path = str(tmp_path / "test.log")
    original = _launch(1) + _launch(2)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(original)

    _trim_log_to_last_launches(path, keep=2)

    with open(path, encoding='utf-8') as f:
        assert f.read() == original


def test_trim_log_to_last_launches_tolerates_a_missing_file(tmp_path):
    _trim_log_to_last_launches(str(tmp_path / "missing.log"), keep=2)  # doesn't raise


def test_get_config_dir_tolerates_a_plain_file_at_that_path(tmp_path, monkeypatch):
    # Real crash (#1427): os.makedirs() raised unhandled if the config
    # path already existed as a plain file, not a directory.
    monkeypatch.setattr(pan_app.platform, 'is_windows', False)
    monkeypatch.setattr(pan_app.platform, 'is_mac', False)
    confdir = tmp_path / ".virtaal"
    confdir.write_text("not a directory")
    monkeypatch.setattr(os.path, 'expanduser', lambda p: str(confdir) if p == '~/.virtaal' else p)

    assert get_config_dir() == str(confdir)  # doesn't raise
    assert confdir.is_file()  # left alone, not clobbered


def test_read_ini_recovering_leaves_a_valid_file_alone(tmp_path):
    path = tmp_path / "settings.ini"
    path.write_text("[general]\nlastdir = /tmp\n")

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path is None
    assert parser.get("general", "lastdir") == "/tmp"
    assert path.exists()


def test_read_ini_recovering_backs_up_a_corrupt_file(tmp_path):
    # Real Windows crash (#3327): a user's virtaal.ini got zero-filled,
    # raising configparser.MissingSectionHeaderError unhandled at
    # startup, before any window could even be drawn.
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 200)

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path == str(path) + ".broken"
    assert not path.exists()
    assert open(backup_path, 'rb').read() == b"\x00" * 200
    assert parser.sections() == []


def test_read_ini_recovering_does_not_clobber_an_existing_backup(tmp_path):
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 10)
    (tmp_path / "settings.ini.broken").write_text("earlier backup")

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path == str(path) + ".broken.2"


def test_settings_recovers_from_a_corrupt_virtaal_ini(tmp_path):
    path = tmp_path / "virtaal.ini"
    path.write_bytes(b"\x00" * 200)

    settings = pan_app.Settings(str(path))

    assert settings.config_recovery_backup == str(path) + ".broken"
    assert settings.config.sections() == settings.sections  # all empty, none lost


def test_save_config_without_a_section_removes_entries_absent_from_the_new_data(tmp_path):
    # #1906: deleting a web look-up entry showed as removed in the UI
    # but stayed in weblookup.ini - each entry is its own section, and
    # a deleted one is simply absent from the dict handed to the next
    # save, not explicitly removed by the caller.
    path = str(tmp_path / 'test.ini')
    pan_app.save_config(path, {'Google': {'url': 'http://google.com'},
                                'Wikipedia': {'url': 'http://wikipedia.org'}})

    pan_app.save_config(path, {'Google': {'url': 'http://google.com'}})

    assert pan_app.load_config(path) == {'Google': {'url': 'http://google.com'}}


def test_save_config_with_a_section_leaves_other_sections_alone(tmp_path):
    path = str(tmp_path / 'test.ini')
    pan_app.save_config(path, {'name': 'af_ZA'}, section='plugin_a')
    pan_app.save_config(path, {'name': 'de_DE'}, section='plugin_b')

    pan_app.save_config(path, {'name': 'af_ZA_updated'}, section='plugin_a')

    conf = pan_app.load_config(path)
    assert conf['plugin_a'] == {'name': 'af_ZA_updated'}
    assert conf['plugin_b'] == {'name': 'de_DE'}


def test_save_config_round_trips_non_ascii_values(tmp_path):
    # save_config()'s own file open had no explicit encoding, so it
    # silently used the platform default (cp1252 on Windows) instead
    # of UTF-8 - crashed outright saving a translated (e.g. Arabic)
    # display_name.
    path = str(tmp_path / 'test.ini')
    pan_app.save_config(path, {'google': {'display_name': 'ﺝﻮﺠﻟ'}})

    assert pan_app.load_config(path) == {'google': {'display_name': 'ﺝﻮﺠﻟ'}}


def test_open_frozen_log_trims_before_appending(tmp_path):
    path = str(tmp_path / "test.log")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(_launch(n) for n in range(1, 4)))

    f = _open_frozen_log(path)
    try:
        f.write(_launch(4))
    finally:
        f.close()

    with open(path, encoding='utf-8') as f:
        kept = f.read()
    assert kept == _launch(2) + _launch(3) + _launch(4)


# UI language selector (translate/virtaal#1492)

def test_ensure_dev_locale_installed_copies_from_the_repo_mo_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(pan_app.platform, 'is_frozen', False)
    repo_root = tmp_path / 'repo'
    (repo_root / 'mo' / 'xx').mkdir(parents=True)
    (repo_root / 'mo' / 'xx' / 'virtaal.mo').write_bytes(b'fake-mo-content')
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(repo_root))
    localedir = tmp_path / 'localedir'

    pan_app._ensure_dev_locale_installed('xx', str(localedir))

    installed = localedir / 'xx' / 'LC_MESSAGES' / 'virtaal.mo'
    assert installed.read_bytes() == b'fake-mo-content'


def test_ensure_dev_locale_installed_is_a_noop_when_already_present(tmp_path, monkeypatch):
    monkeypatch.setattr(pan_app.platform, 'is_frozen', False)
    localedir = tmp_path / 'localedir'
    existing = localedir / 'xx' / 'LC_MESSAGES'
    existing.mkdir(parents=True)
    (existing / 'virtaal.mo').write_bytes(b'already-there')
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'unused'))

    pan_app._ensure_dev_locale_installed('xx', str(localedir))

    assert (existing / 'virtaal.mo').read_bytes() == b'already-there'


def test_ensure_dev_locale_installed_does_nothing_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(pan_app.platform, 'is_frozen', True)
    repo_root = tmp_path / 'repo'
    (repo_root / 'mo' / 'xx').mkdir(parents=True)
    (repo_root / 'mo' / 'xx' / 'virtaal.mo').write_bytes(b'fake')
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(repo_root))
    localedir = tmp_path / 'localedir'

    pan_app._ensure_dev_locale_installed('xx', str(localedir))

    assert not (localedir / 'xx').exists()


def test_ensure_dev_locale_installed_tolerates_a_missing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(pan_app.platform, 'is_frozen', False)
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'nonexistent'))
    localedir = tmp_path / 'localedir'

    pan_app._ensure_dev_locale_installed('xx', str(localedir))  # should not raise

    assert not (localedir / 'xx').exists()


def test_ensure_dev_locale_installed_compiles_the_po_when_no_mo_was_ever_built(tmp_path, monkeypatch):
    # A checkout that's never run `pip install -e .` (so setup.py's own
    # mo/ compile step never ran) still has po/<lang>.po - translate-
    # toolkit (a hard dependency already) can compile that directly.
    monkeypatch.setattr(pan_app.platform, 'is_frozen', False)
    repo_root = tmp_path / 'repo'
    (repo_root / 'po').mkdir(parents=True)
    (repo_root / 'po' / 'xx.po').write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Kgotso"\n',
        encoding='utf-8')
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(repo_root))
    localedir = tmp_path / 'localedir'

    pan_app._ensure_dev_locale_installed('xx', str(localedir))

    import gettext
    with open(localedir / 'xx' / 'LC_MESSAGES' / 'virtaal.mo', 'rb') as f:
        translation = gettext.GNUTranslations(f)
    assert translation.gettext('Hello') == 'Kgotso'


def test_get_available_ui_languages_has_no_system_default_entry_of_its_own(tmp_path, monkeypatch):
    # pan_app.py is in po/POTFILES.skip - a label here would never be
    # translatable. The caller (prefsview.py) adds one instead.
    monkeypatch.setattr(pan_app.platform, 'locale_dir', str(tmp_path / 'prefix' / 'share' / 'locale'))
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'repo'))

    langs = pan_app.get_available_ui_languages()

    assert langs == []


def test_get_available_ui_languages_finds_languages_in_either_location(tmp_path, monkeypatch):
    # A packaged install populates platform.locale_dir; a dev checkout
    # instead has the repo's own flat mo/<code>/virtaal.mo (see
    # _ensure_dev_locale_installed) - both need to be offered.
    locale_dir = tmp_path / 'prefix' / 'share' / 'locale'
    repo = tmp_path / 'repo'
    (locale_dir / 'fr' / 'LC_MESSAGES').mkdir(parents=True)
    (locale_dir / 'fr' / 'LC_MESSAGES' / 'virtaal.mo').write_bytes(b'x')
    (repo / 'mo' / 'af').mkdir(parents=True)
    (repo / 'mo' / 'af' / 'virtaal.mo').write_bytes(b'x')
    monkeypatch.setattr(pan_app.platform, 'locale_dir', str(locale_dir))
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(repo))

    langs = dict(pan_app.get_available_ui_languages())

    assert langs['fr'] == 'French'
    assert langs['af'] == 'Afrikaans'


def test_get_available_ui_languages_cleans_up_a_semicolon_joined_name(tmp_path, monkeypatch):
    # toolkit's own raw name for 'nso' is the semicolon-joined MARC/ISO
    # 639-2 entry "Pedi; Sepedi; Northern Sotho" - not something to
    # show a user as-is.
    locale_dir = tmp_path / 'prefix' / 'share' / 'locale'
    (locale_dir / 'nso' / 'LC_MESSAGES').mkdir(parents=True)
    (locale_dir / 'nso' / 'LC_MESSAGES' / 'virtaal.mo').write_bytes(b'x')
    monkeypatch.setattr(pan_app.platform, 'locale_dir', str(locale_dir))
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'repo'))

    langs = dict(pan_app.get_available_ui_languages())

    assert langs['nso'] == 'Northern Sotho'


def test_get_available_ui_languages_falls_back_to_the_code_for_an_unknown_language(tmp_path, monkeypatch):
    locale_dir = tmp_path / 'prefix' / 'share' / 'locale'
    (locale_dir / 'zzz' / 'LC_MESSAGES').mkdir(parents=True)
    (locale_dir / 'zzz' / 'LC_MESSAGES' / 'virtaal.mo').write_bytes(b'x')
    monkeypatch.setattr(pan_app.platform, 'locale_dir', str(locale_dir))
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'repo'))

    langs = dict(pan_app.get_available_ui_languages())

    assert langs['zzz'] == 'zzz'


def test_get_available_ui_languages_excludes_pseudo_translations(tmp_path, monkeypatch):
    # devsupport/pseudo-translation's own generated locales - a testing
    # aid, not a real language a user would pick in Preferences.
    locale_dir = tmp_path / 'prefix' / 'share' / 'locale'
    for code in ('pseudo', 'pseudo-bidi', 'af'):
        (locale_dir / code / 'LC_MESSAGES').mkdir(parents=True)
        (locale_dir / code / 'LC_MESSAGES' / 'virtaal.mo').write_bytes(b'x')
    monkeypatch.setattr(pan_app.platform, 'locale_dir', str(locale_dir))
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'repo'))

    langs = dict(pan_app.get_available_ui_languages())

    assert set(langs) == {'af'}


# _read_ini_recovering()'s remaining branches #

def test_read_ini_recovering_clears_sections_already_on_the_parser(tmp_path):
    # A parser handed in already populated (e.g. re-reading into one
    # that outlived an earlier successful read) must not keep stale
    # sections once the file underneath it turns out to be corrupt.
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 200)
    parser = pan_app.ConfigParser.RawConfigParser()
    parser.add_section('stale')

    _read_ini_recovering(parser, str(path))

    assert parser.sections() == []


def test_read_ini_recovering_tolerates_a_failed_backup_rename(tmp_path, monkeypatch):
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 200)
    monkeypatch.setattr(pan_app.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError()))
    parser = pan_app.ConfigParser.RawConfigParser()

    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path is None
    assert path.exists()  # never actually moved


# get_config_dir()'s Windows branch #

def test_get_config_dir_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)
    monkeypatch.setenv('APPDATA', str(tmp_path))

    confdir = get_config_dir()

    assert confdir == os.path.join(str(tmp_path), 'Virtaal')
    assert os.path.isdir(confdir)


# _repo_root() #

def test_repo_root_resolves_to_the_real_checkout_root():
    root = pan_app._repo_root()

    assert os.path.isdir(os.path.join(root, 'virtaal'))
    assert os.path.isfile(os.path.join(root, 'pyproject.toml'))


# name() #

def test_name_tolerates_a_missing_pwd_module(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'pwd', None)  # forces `import pwd` to raise ImportError

    result = pan_app.name()

    assert result  # falls back to plain getpass.getuser()


# get_locale_lang() #

def test_get_locale_lang_uses_osx_lang_when_locale_is_unset_on_mac(monkeypatch):
    monkeypatch.setattr(pan_app.locale, 'getdefaultlocale', lambda *a: (None, None))
    monkeypatch.setattr(pan_app.platform, 'is_mac', True)
    monkeypatch.setattr(pan_app, 'osx_lang', lambda: 'fr_FR')

    assert pan_app.get_locale_lang() == pan_app.data.simplify_to_common('fr_FR')


def test_get_locale_lang_falls_back_to_en_on_error(monkeypatch, caplog):
    def _raise(*a):
        raise RuntimeError('no locale')
    monkeypatch.setattr(pan_app.locale, 'getdefaultlocale', _raise)

    with caplog.at_level(logging.WARNING):
        result = pan_app.get_locale_lang()

    assert result == 'en'
    assert any('no locale' in r.message for r in caplog.records)


# get_default_font() #

def test_get_default_font_falls_back_to_gio_when_gconf_is_unavailable(monkeypatch):
    import gi
    real_require_version = gi.require_version
    def fake_require_version(namespace, version):
        if namespace == 'GConf':
            raise ImportError('no GConf')
        return real_require_version(namespace, version)
    monkeypatch.setattr(gi, 'require_version', fake_require_version)

    font = pan_app.get_default_font()

    assert font  # the real system GSettings font name, whatever it is


def test_get_default_font_falls_back_to_gtk_when_gconf_raises_unexpectedly(monkeypatch):
    # The real, unmocked behaviour on a system with no GConf typelib at
    # all: gi.require_version() itself raises ValueError, not
    # ImportError - only the generic `except Exception` catches it.
    import gi
    real_require_version = gi.require_version
    def fake_require_version(namespace, version):
        if namespace == 'GConf':
            raise ValueError('Namespace GConf not available')
        return real_require_version(namespace, version)
    monkeypatch.setattr(gi, 'require_version', fake_require_version)

    font = pan_app.get_default_font()

    assert font.startswith('monospace ')


# Settings #

def test_settings_raises_for_a_missing_explicit_filename(tmp_path):
    with pytest.raises(Exception):
        pan_app.Settings(str(tmp_path / 'does-not-exist.ini'))


def test_settings_write_creates_the_config_directory_if_missing(tmp_path):
    seed = tmp_path / 'seed.ini'
    seed.write_text('')
    settings = pan_app.Settings(str(seed))
    new_path = tmp_path / 'newdir' / 'virtaal.ini'
    settings.filename = str(new_path)

    settings.write()

    assert new_path.is_file()


# save_config() #

def test_save_config_joins_list_values(tmp_path):
    path = str(tmp_path / 'test.ini')

    pan_app.save_config(path, {'section': {'items': ['a', 'b', 'c']}})

    assert pan_app.load_config(path, 'section')['items'] == 'a,b,c'


# set_ui_language() #

def test_set_ui_language_installs_the_translation_and_updates_the_module_global(monkeypatch):
    installed = []
    fake_translation = SimpleNamespace(install=lambda: installed.append(True))
    monkeypatch.setattr(pan_app.gettext, 'translation',
                         lambda *a, **kw: fake_translation)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)  # skips bind_libintl_posix

    pan_app.set_ui_language('af')

    assert installed == [True]
    assert pan_app.ui_language == 'af'


def test_set_ui_language_binds_libintl_on_non_windows(monkeypatch):
    fake_translation = SimpleNamespace(install=lambda: None)
    monkeypatch.setattr(pan_app.gettext, 'translation', lambda *a, **kw: fake_translation)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', False)
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/fake/venv/share/locale')
    bound = []
    monkeypatch.setattr(pan_app, 'bind_libintl_posix', bound.append)

    pan_app.set_ui_language('af')

    assert bound == ['/fake/venv/share/locale']


def test_set_ui_language_uses_platform_locale_dir(monkeypatch):
    # Real bug this guards against: pan_app.py used to compute this
    # itself from sys.prefix directly, which is wrong in a frozen
    # build (see test_platform.py's own coverage of that) - it must go
    # through platform.locale_dir instead, not re-derive it.
    seen_localedirs = []
    fake_translation = SimpleNamespace(install=lambda: None)

    def fake_gettext_translation(domain, localedir, languages, fallback):
        seen_localedirs.append(localedir)
        return fake_translation

    monkeypatch.setattr(pan_app.gettext, 'translation', fake_gettext_translation)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)  # skips bind_libintl_posix
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/fake/bundle/share/locale')

    pan_app.set_ui_language('af')

    assert seen_localedirs == ['/fake/bundle/share/locale']


def test_set_ui_language_tolerates_an_unsupported_locale(monkeypatch):
    fake_translation = SimpleNamespace(install=lambda: None)
    monkeypatch.setattr(pan_app.gettext, 'translation', lambda *a, **kw: fake_translation)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)
    monkeypatch.setattr(pan_app.locale, 'setlocale',
                         lambda *a: (_ for _ in ()).throw(pan_app.locale.Error()))

    pan_app.set_ui_language('xx_XX')  # must not raise

    assert pan_app.ui_language == 'xx_XX'


def test_set_ui_language_aliases_en_to_en_us(monkeypatch):
    seen = {}

    def fake_gettext_translation(domain, localedir, languages, fallback):
        seen['languages'] = languages
        seen['fallback'] = fallback
        return SimpleNamespace(install=lambda: None)

    monkeypatch.setattr(pan_app.gettext, 'translation', fake_gettext_translation)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)

    pan_app.set_ui_language('en')

    assert seen['languages'] == ['en_US']
    # 'en' is this module's canonical "untranslated UI" value elsewhere
    # (see the 'system' and module-level fallbacks) - en_US collapses
    # back to it rather than being reported as a one-off.
    assert pan_app.ui_language == 'en'


def test_set_ui_language_en_us_does_not_raise_without_a_catalog(monkeypatch):
    # #3774: English is Virtaal's own source language and ships no
    # catalog of its own - unlike any other requested language, a
    # missing catalog for it isn't a typo and must not raise.
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/nonexistent/locale/dir')

    pan_app.set_ui_language('en_US')  # must not raise OSError

    assert pan_app.ui_language == 'en'


def test_set_ui_language_other_missing_catalogs_still_raise(monkeypatch):
    # Only en/en_US get the "no catalog is fine" treatment - any other
    # requested language with no catalog is still very likely a typo.
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/nonexistent/locale/dir')

    with pytest.raises(OSError):
        pan_app.set_ui_language('xx_XX_bogus')


def test_set_ui_language_system_ignores_a_saved_preference(monkeypatch):
    # --lang=system must re-resolve the OS locale even when a uilang
    # preference is already saved/installed.
    installed = []
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: installed.append(a))
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.setattr('builtins._', lambda s: s or 'PO header')  # a real catalog is loaded
    monkeypatch.delenv('LANGUAGE', raising=False)
    pan_app.ui_language = 'en'  # simulate an already-installed override

    pan_app.set_ui_language('system')

    assert installed == [('virtaal',)]
    assert pan_app.ui_language == 'fr'


def test_set_ui_language_system_reports_en_without_a_real_catalog(monkeypatch):
    # Matches startup's own `if _(''): ... else: 'en'` guard -
    # a resolved system locale with no real catalog must report 'en',
    # not the untranslated locale code (aboutdialog.py keys RTL layout
    # off ui_language).
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'ar')
    monkeypatch.setattr('builtins._', lambda s: s)  # NullTranslations-style passthrough
    monkeypatch.delenv('LANGUAGE', raising=False)

    pan_app.set_ui_language('system')

    assert pan_app.ui_language == 'en'


def test_set_ui_language_system_self_heals_a_dev_checkout(monkeypatch):
    # The explicit-language branch below self-heals a dev
    # checkout's uncompiled catalog (_ensure_dev_locale_installed) -
    # --lang=system must do the same for its best-guess language, or
    # it silently stays untranslated where --lang=<code> would work.
    seen = []
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: seen.append((lang, localedir)))
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/fake/venv/share/locale')
    monkeypatch.delenv('LANGUAGE', raising=False)

    pan_app.set_ui_language('system')

    assert seen == [('fr', '/fake/venv/share/locale')]


def test_set_ui_language_system_clears_a_language_env_override(monkeypatch):
    # fix_locale(lang) sets os.environ['LANGUAGE'] unconditionally, even
    # on POSIX - gettext checks LANGUAGE before LC_ALL/LANG, so
    # --lang=system must undo that override or it keeps resolving to
    # the previous explicit language.
    monkeypatch.setattr(pan_app, '_ORIGINAL_LOCALE_ENV', {'LANGUAGE': None, 'LANG': None, 'LC_ALL': None})
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.setenv('LANGUAGE', 'af')

    pan_app.set_ui_language('system')

    assert 'LANGUAGE' not in os.environ


def test_set_ui_language_system_restores_the_original_locale_env(monkeypatch):
    # Also covers Windows, where fix_locale(lang=None) recomputes LANG/
    # LC_ALL/LANGUAGE via _getlang(), which reads LANG back - a stale
    # LANG left over from an earlier explicit language would otherwise
    # poison that resolution too.
    monkeypatch.setattr(pan_app, '_ORIGINAL_LOCALE_ENV', {'LANGUAGE': 'de', 'LANG': 'de', 'LC_ALL': 'de'})
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'de')
    monkeypatch.setenv('LANGUAGE', 'af')
    monkeypatch.setenv('LANG', 'af')
    monkeypatch.setenv('LC_ALL', 'af')

    pan_app.set_ui_language('system')

    assert os.environ['LANGUAGE'] == 'de'
    assert os.environ['LANG'] == 'de'
    assert os.environ['LC_ALL'] == 'de'


def test_set_ui_language_system_uses_platform_locale_dir(monkeypatch):
    # Same bug class as test_set_ui_language_uses_platform_locale_dir:
    # gettext's own default search path misses a venv's installed
    # translations - must go through platform.locale_dir explicitly
    # here too.
    seen_localedirs = []

    def fake_gettext_install(domain, localedir):
        seen_localedirs.append(localedir)

    monkeypatch.setattr(pan_app.gettext, 'install', fake_gettext_install)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.setattr(pan_app.platform, 'is_windows', True)  # skips bind_libintl_posix
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/fake/venv/share/locale')
    monkeypatch.delenv('LANGUAGE', raising=False)

    pan_app.set_ui_language('system')

    assert seen_localedirs == ['/fake/venv/share/locale']


def test_set_ui_language_system_binds_libintl_on_non_windows(monkeypatch):
    # A previously-bound explicit language (e.g. a saved uilang
    # preference already installed at startup) needs libintl's
    # C-level textdomain re-pointed too, or Gtk.Builder-sourced
    # strings stay in that old language.
    monkeypatch.setattr(pan_app.gettext, 'install', lambda *a, **kw: None)
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale', lambda *a: None)
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.setattr(pan_app.platform, 'is_windows', False)
    monkeypatch.setattr(pan_app.platform, 'locale_dir', '/fake/venv/share/locale')
    bound = []
    monkeypatch.setattr(pan_app, 'bind_libintl_posix', bound.append)
    monkeypatch.delenv('LANGUAGE', raising=False)

    pan_app.set_ui_language('system')

    assert bound == ['/fake/venv/share/locale']


def test_set_ui_language_system_tolerates_an_unsupported_locale(monkeypatch):
    monkeypatch.setattr(pan_app, 'fix_locale', lambda lang=None: None)
    monkeypatch.setattr(pan_app, '_ensure_dev_locale_installed', lambda lang, localedir: None)
    monkeypatch.setattr(pan_app.locale, 'setlocale',
                         lambda *a: (_ for _ in ()).throw(pan_app.locale.Error()))
    monkeypatch.setattr(pan_app, 'get_locale_lang', lambda: 'fr')
    monkeypatch.delenv('LANGUAGE', raising=False)

    pan_app.set_ui_language('system')  # must not raise

    # _install_system_ui_language()'s own locale.Error recovery installs
    # an untranslated passthrough _, so this matches the "no real
    # catalog" case: 'en', not the raw locale code.
    assert pan_app.ui_language == 'en'
