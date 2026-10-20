#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Pango
from translate.storage import mo

from virtaal.support import fontcoverage

# Unassigned, so no font has a glyph for it.
NO_GLYPH = '͸'


def _write_mo(path, translations):
    store = mo.mofile()
    store.addsourceunit('').target = 'Content-Type: text/plain; charset=UTF-8\n'
    for source, target in translations.items():
        store.addsourceunit(source).target = target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(store))


def test_shipped_languages_finds_both_layouts(tmp_path):
    _write_mo(tmp_path / 'af' / 'LC_MESSAGES' / 'virtaal.mo', {'Open': 'Oop'})
    _write_mo(tmp_path / 'de' / 'virtaal.mo', {'Open': 'Öffnen'})
    _write_mo(tmp_path / 'pseudo' / 'virtaal.mo', {'Open': '[Open]'})
    _write_mo(tmp_path / 'fr' / 'LC_MESSAGES' / 'gtk30.mo', {'Open': 'Ouvrir'})
    assert fontcoverage.shipped_languages(str(tmp_path)) == {
        'af': str(tmp_path / 'af' / 'LC_MESSAGES'),
        'de': str(tmp_path / 'de'),
    }


def test_shipped_languages_without_the_folder(tmp_path):
    assert fontcoverage.shipped_languages(str(tmp_path / 'missing')) == {}


def test_messages_reads_every_catalog(tmp_path):
    _write_mo(tmp_path / 'virtaal.mo', {'Open': 'Oop'})
    _write_mo(tmp_path / 'gtk30.mo', {'Cancel': 'Kanselleer'})
    (tmp_path / 'notes.txt').write_text('not a catalog')
    assert fontcoverage.messages(str(tmp_path)) == {'Oop', 'Kanselleer'}


def test_current_platform(monkeypatch):
    from virtaal.common.platform import platform
    for is_mac, is_windows, expected in ((True, False, 'macos'), (False, True, 'windows'), (False, False, 'linux')):
        monkeypatch.setattr(platform, 'is_mac', is_mac)
        monkeypatch.setattr(platform, 'is_windows', is_windows)
        assert fontcoverage.current_platform() == expected


def test_missing_names_the_character():
    renderer = fontcoverage.Renderer(Pango.FontDescription.from_string('Sans 10'), 'en')
    assert renderer.missing('Open the file') == set()
    assert renderer.missing('Open %s file' % NO_GLYPH) == {NO_GLYPH}


def test_check_includes_language_names(tmp_path):
    _write_mo(tmp_path / 'af' / 'virtaal.mo', {'Open': 'Oop'})
    font_descs = {'ui': Pango.FontDescription.from_string('Sans 10')}
    assert fontcoverage.check(str(tmp_path), font_descs) == {}
    report = fontcoverage.check(str(tmp_path), font_descs, endonym=lambda code: 'Afri%skaans' % NO_GLYPH)
    assert report == {('ui', NO_GLYPH): {'af'}}


def test_format_report_counts_only_new_gaps():
    font_descs = {'ui': Pango.FontDescription.from_string('Sans 10')}
    report = {('ui', 'a'): {'af', 'de'}, ('ui', 'b'): {'af', 'ja'}, ('editor', 'b'): {'af'}}
    known = [
        (1, 'macos', 'ui', 'a', fontcoverage.ALL),
        (2, 'macos', 'ui', fontcoverage.span('b', 'c'), ['ja']),
        (3, 'windows', 'editor', 'b', fontcoverage.ALL),
        (4, 'macos', 'editor', 'z', fontcoverage.ALL),
    ]
    text, new = fontcoverage.format_report(report, font_descs, 'macos', known)
    assert new == 2
    assert 'ui font, af de: known, #1: a (U+0061 LATIN SMALL LETTER A)\n' in text
    assert 'ui font, ja: known, #2: b (U+0062 LATIN SMALL LETTER B)\n' in text
    assert 'ui font, af: NEW: b (U+0062 LATIN SMALL LETTER B)\n' in text
    assert 'editor font, af: NEW: b (U+0062 LATIN SMALL LETTER B)\n' in text
    assert ('editor font: #4 displays now: z (U+007A LATIN SMALL LETTER Z); if it is fixed, remove it from KNOWN_GAPS\n'
            in text)
    assert '#2 displays now' not in text
    assert text.endswith('new: 2\n')


def test_missing_skips_control_characters():
    renderer = fontcoverage.Renderer(Pango.FontDescription.from_string('Sans 10'), 'en')
    assert renderer.missing('ls \x1b[1mfile\x1b[0m') == set()


def test_fonts_add_the_platform_fallbacks():
    from virtaal.views import rendering
    font_descs = fontcoverage.fonts()
    assert set(font_descs) == {'ui', 'editor'}
    for font in font_descs.values():
        assert font.get_family().split(',')[1:] == list(rendering.font_fallbacks())


def test_main_writes_the_report(tmp_path, monkeypatch):
    from virtaal.common import pan_app
    _write_mo(tmp_path / 'mo' / 'af' / 'virtaal.mo', {'Open': 'Oop'})
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path))
    monkeypatch.setattr(fontcoverage, 'KNOWN_GAPS', [])
    out = tmp_path / 'report.txt'
    fontcoverage.main(['fontcoverage', str(out)])
    text = out.read_text(encoding='utf-8')
    assert text.startswith('font ui: ')
    assert text.endswith('new: 0\n')


def test_main_prints_the_report_without_a_file(tmp_path, monkeypatch, capsys):
    from virtaal.common import pan_app
    _write_mo(tmp_path / 'mo' / 'af' / 'virtaal.mo', {'Open': 'Oop'})
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path))
    monkeypatch.setattr(fontcoverage, 'KNOWN_GAPS', [])
    fontcoverage.main(['fontcoverage'])
    assert capsys.readouterr().out.endswith('new: 0\n')


def test_run_module_reads_the_package_catalogs(tmp_path, monkeypatch):
    """As virtaal --run-module runs it in a package, which has no mo/."""
    import runpy
    import sys

    from virtaal.common import pan_app
    from virtaal.common.platform import platform
    _write_mo(tmp_path / 'locale' / 'af' / 'LC_MESSAGES' / 'virtaal.mo', {'Open': 'Oop%s' % NO_GLYPH})
    monkeypatch.setattr(pan_app, '_repo_root', lambda: str(tmp_path / 'checkout'))
    monkeypatch.setattr(platform, 'locale_dir', str(tmp_path / 'locale'))
    out = tmp_path / 'report.txt'
    monkeypatch.setattr(sys, 'argv', ['fontcoverage', str(out)])
    runpy.run_module('virtaal.support.fontcoverage', run_name='__main__')
    assert out.read_text(encoding='utf-8').endswith('new: 2\n')  # both fonts
