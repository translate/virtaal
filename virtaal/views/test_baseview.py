import ctypes
import ctypes.util

import gi

gi.require_version('Gtk', '3.0')

from virtaal.views.baseview import BaseView, _builders


def test_load_builder_file_translates_translatable_markup(tmp_path, monkeypatch):
    if ctypes.util.find_library('intl') is None:
        import pytest
        pytest.skip("no libintl available to bind against")

    monkeypatch.setattr('virtaal.views.baseview._builders', {})

    ui_dir = tmp_path / 'share' / 'virtaal'
    ui_dir.mkdir(parents=True)
    ui_file = ui_dir / 'probe.ui'
    ui_file.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<interface>\n'
        '  <object class="GtkLabel" id="lbl">\n'
        '    <property name="label" translatable="yes">Hello</property>\n'
        '  </object>\n'
        '</interface>\n',
        encoding='utf-8')

    po_file = tmp_path / 'probedomain.po'
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Hallo"\n',
        encoding='utf-8')
    mo_dir = tmp_path / 'locale' / 'af' / 'LC_MESSAGES'
    mo_dir.mkdir(parents=True)
    from translate.tools.pocompile import convertmo
    with open(po_file, 'rb') as infile, open(mo_dir / 'probedomain.mo', 'w') as outfile:
        convertmo(infile, outfile, None)

    libintl = ctypes.CDLL(ctypes.util.find_library('intl'))
    libintl.bindtextdomain(b'probedomain', str(tmp_path / 'locale').encode())
    libintl.bind_textdomain_codeset(b'probedomain', b'UTF-8')

    monkeypatch.setenv('LANGUAGE', 'af')

    monkeypatch.setattr(
        'virtaal.common.pan_app.get_abs_data_filename',
        lambda path_parts: str(tmp_path.joinpath(*path_parts)))

    builder = BaseView.load_builder_file(['share', 'virtaal', 'probe.ui'], domain='probedomain')

    assert builder.get_object('lbl').get_label() == 'Hallo'


def test_load_builder_file_caches_by_path(monkeypatch):
    _builders.clear()
    monkeypatch.setattr(
        'virtaal.common.pan_app.get_abs_data_filename',
        lambda path_parts: '/dev/null')

    class _FakeBuilder:
        def set_translation_domain(self, domain):
            pass

        def add_from_file(self, path):
            pass

    monkeypatch.setattr('virtaal.views.baseview.Builder', _FakeBuilder)

    first = BaseView.load_builder_file(['a', 'b'], domain='x')
    second = BaseView.load_builder_file(['a', 'b'], domain='x')

    assert first is second
