#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib
import os
import runpy
import sys
import types

import pytest

from virtaal.support.enchant_compat import (
    SAMPLES,
    bundle_roots,
    duplicate_libraries,
    enchant_tag,
    foreign_libraries,
    import_enchant,
    loaded_libraries,
    mapped_libraries,
    marked_words,
    sample_text,
    self_check,
    spelling_libraries,
    system_dirs,
)

needs_enchant = pytest.mark.skipif(import_enchant() is None, reason="pyenchant is not available")


def _gtkspell_available():
    try:
        import gi
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def _report(text):
    return dict(line.split(': ', 1) for line in text.splitlines())


def test_leftover_enchant_directory_is_not_enchant(monkeypatch, tmp_path):
    """#4313: an "enchant" directory with no __init__.py imports as an
    empty namespace package."""
    (tmp_path / 'enchant' / '__pycache__').mkdir(parents=True)
    monkeypatch.delitem(sys.modules, 'enchant', raising=False)
    # A real pyenchant anywhere on sys.path would win over the directory.
    monkeypatch.setattr(sys, 'path', [str(tmp_path)])
    importlib.invalidate_caches()
    assert import_enchant() is None


def test_missing_enchant(monkeypatch):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    assert import_enchant() is None


def test_usable_enchant(monkeypatch):
    enchant = types.ModuleType('enchant')
    enchant.dict_exists = enchant.list_languages = enchant.get_user_config_dir = lambda *a: None
    monkeypatch.setitem(sys.modules, 'enchant', enchant)
    assert import_enchant() is enchant


def test_self_check_without_enchant(monkeypatch):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    assert self_check('en_US') == 'enchant: none\n'


# What the packaged builds' smoke tests run, here against the real libraries.

@needs_enchant
def test_self_check_reports_the_enchant_library_and_providers():
    import enchant
    from enchant import _enchant

    report = _report(self_check('en_US'))

    assert report['enchant'] == _enchant.enchant_lib_path
    assert report['providers'] == ' '.join(sorted(p.name for p in enchant.Broker().describe()))
    assert report['dictionary'] == str(enchant.dict_exists('en_US'))


@needs_enchant
def test_self_check_spell_checks_with_an_installed_dictionary():
    import enchant
    if not (enchant.dict_exists('en_US') and _gtkspell_available()):
        pytest.skip("needs GtkSpell and an en_US dictionary")

    assert _report(self_check('en_US'))['gtkspell'] == 'ok'


@needs_enchant
def test_self_check_reports_a_language_without_a_dictionary():
    report = _report(self_check('xx_YY'))

    assert report['dictionary'] == 'False'
    assert report['gtkspell'] != 'ok'
    if _gtkspell_available():
        assert 'xx_YY' in report['gtkspell']


def test_run_module_prints_the_report(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    monkeypatch.setattr(sys, 'argv', ['enchant_compat', 'xx_YY'])
    # run_module() warns if the module is already imported.
    monkeypatch.delitem(sys.modules, 'virtaal.support.enchant_compat')

    runpy.run_module('virtaal.support.enchant_compat', run_name='__main__')

    assert capsys.readouterr().out == 'enchant: none\n'


@pytest.mark.parametrize('code, tag', [
    ('af', 'af'),
    ('nl_BE', 'nl_BE'),
    ('en-GB', 'en_GB'),
    ('ca@valencia', 'ca_VALENCIA'),
    ('sr@latin', 'sr_LATIN'),
    ('sr_Latn', 'sr_LATN'),
    ('sr_Latn_RS', 'sr_LATNRS'),
    ('ca_ES_valencia', 'ca_ESVALENCIA'),
])
def test_enchant_tag(code, tag):
    # Enchant finds only "language_PART" names (#4665).
    assert enchant_tag(code) == tag


@needs_enchant
def test_self_check_marks_the_misspelt_word():
    import enchant
    if not (enchant.dict_exists('en_US') and _gtkspell_available()):
        pytest.skip("needs GtkSpell and an en_US dictionary")

    report = _report(self_check('en_US'))

    assert report['marked'] == 'tset'
    assert report['unknown'] == 'tset'


def test_run_module_writes_the_report_to_a_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    output = tmp_path / 'enchant.txt'
    monkeypatch.setattr(sys, 'argv', ['enchant_compat', 'xx_YY', str(output)])
    monkeypatch.delitem(sys.modules, 'virtaal.support.enchant_compat')

    runpy.run_module('virtaal.support.enchant_compat', run_name='__main__')

    assert output.read_text(encoding='utf-8') == 'enchant: none\n'
    assert capsys.readouterr().out == ''


def test_marked_words():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    buffer = Gtk.TextBuffer()
    buffer.set_text('one twu three fuor')
    tag = buffer.create_tag('gtkspell-misspelled')
    for start, end in ((4, 7), (14, 18)):
        buffer.apply_tag(tag, buffer.get_iter_at_offset(start), buffer.get_iter_at_offset(end))

    assert marked_words(buffer) == ['twu', 'fuor']
    assert marked_words(Gtk.TextBuffer()) == []


def test_sample_text_by_language():
    assert sample_text('en_GB') == SAMPLES['en']
    assert sample_text('hu_HU') == SAMPLES['hu']
    assert sample_text('xx') == SAMPLES['en']


@pytest.mark.parametrize('platform, roots, system, paths, foreign', [
    # A build machine's Homebrew copy, next to the bundle's and the OS's.
    ('darwin', ['/A/Virtaal.app/Contents'], ['/usr/lib', '/System'],
     ['/A/Virtaal.app/Contents/Frameworks/libenchant-2.2.dylib', '/usr/lib/libSystem.B.dylib',
      '/System/Library/Frameworks/AppKit.framework/AppKit', '/opt/homebrew/lib/libgtkspell3-3.0.dylib',
      '/A/Virtaal.app/Contentsx/libfoo.dylib'],
     ['/opt/homebrew/lib/libgtkspell3-3.0.dylib', '/A/Virtaal.app/Contentsx/libfoo.dylib']),
    ('win32', [r'C:\Program Files\Virtaal'], [r'C:\Windows'],
     [r'C:\Program Files\Virtaal\libgtkspell3-3-0.dll', r'c:\windows\System32\KERNEL32.DLL', r'C:\gtk\bin\gtk-3-vs17.dll'],
     [r'C:\gtk\bin\gtk-3-vs17.dll']),
    # The AppImage uses the host's libc, but never the host's enchant.
    ('linux', ['/tmp/.mount_x'], ['/lib', '/usr/lib'],
     ['/tmp/.mount_x/libenchant-2.so.2', '/usr/lib/x86_64-linux-gnu/libc.so.6',
      '/usr/lib/x86_64-linux-gnu/libenchant-2.so.2', '/opt/other/libfoo.so'],
     ['/usr/lib/x86_64-linux-gnu/libenchant-2.so.2', '/opt/other/libfoo.so']),
])
def test_foreign_libraries(platform, roots, system, paths, foreign):
    assert foreign_libraries(paths, roots, system, platform) == foreign


def test_system_dirs():
    assert system_dirs('win32', {'SystemRoot': r'D:\WINDOWS'}) == [r'D:\WINDOWS']
    assert '/System' in system_dirs('darwin')
    assert '/usr/lib' in system_dirs('linux')


def test_spelling_libraries():
    paths = ['/b/libenchant-2.so.2', '/b/enchant_hunspell.so', '/b/libgtkspell3-3.so.0', '/b/libgtk-3.so.0']
    assert spelling_libraries(paths) == paths[:3]


def test_loaded_libraries_include_the_c_library():
    names = [os.path.basename(p).lower() for p in loaded_libraries()]
    c_library = {'darwin': 'libsystem', 'win32': 'kernel32'}.get(sys.platform, 'libc.so')
    assert any(name.startswith(c_library) for name in names)


def test_bundle_roots_from_source(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.delenv('FLATPAK_ID', raising=False)
    assert bundle_roots() is None
    monkeypatch.setenv('FLATPAK_ID', 'io.github.translate.Virtaal')
    assert bundle_roots() == ['/app', '/usr']


def test_duplicate_libraries():
    paths = ['/a/libglib-2.0.0.dylib', '/b/libgtk-3.0.dylib', '/c/libglib-2.0.0.dylib',
             '/usr/lib/liblzma.5.dylib', '/a/liblzma.5.dylib']
    assert duplicate_libraries(paths, ['/usr/lib'], 'darwin') == [paths[0], paths[2]]
    assert duplicate_libraries(paths[:2], ['/usr/lib'], 'darwin') == []
    windows = [r'C:\x\FOO.dll', r'C:\y\foo.dll', r'C:\Windows\foo.dll']
    assert duplicate_libraries(windows, [r'C:\Windows'], 'win32') == windows[:2]


def test_mapped_libraries():
    maps = [
        '7f00-7f10 r-xp 00000000 08:01 1 /usr/lib/x86_64-linux-gnu/libc.so.6\n',
        '7f10-7f20 r--p 00000000 08:01 2 /app/lib/libgtkspell3-3.so.0.2.0\n',
        '7f20-7f30 r--p 00000000 08:01 3 /usr/lib/enchant-2/enchant_hunspell.so\n',
        '7f30-7f40 r--p 00000000 08:01 4 /etc/ld.so.cache (deleted)\n',
        '7f40-7f50 rw-p 00000000 00:00 0 [heap]\n',
        '7f50-7f60 r--p 00000000 08:01 5 /usr/share/locale/de/LC_MESSAGES/gtk30.mo\n',
    ]
    assert mapped_libraries(maps) == [
        '/app/lib/libgtkspell3-3.so.0.2.0', '/usr/lib/enchant-2/enchant_hunspell.so',
        '/usr/lib/x86_64-linux-gnu/libc.so.6',
    ]
