#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import tempfile
from io import BytesIO
from types import SimpleNamespace

import pytest

from virtaal.support import project as project_module
from virtaal.support.project import Project, split_extensions
from virtaal.support.projstore import ProjectStore

# split_extensions() #

def test_split_extensions_strips_a_single_three_letter_extension():
    assert split_extensions('document.odt') == ('document', 'odt')


def test_split_extensions_keeps_po_and_properties_despite_being_longer_than_three_letters():
    assert split_extensions('messages.po') == ('messages', 'po')
    assert split_extensions('strings.properties') == ('strings', 'properties')


def test_split_extensions_chains_consecutive_three_letter_extensions():
    assert split_extensions('archive.tar.zip') == ('archive', 'tar.zip')


def test_split_extensions_stops_at_the_first_non_three_letter_part_from_the_end():
    # 'gz' is only two letters, so scanning from the end stops there
    # immediately - the whole name is treated as having no extension at
    # all, not even the 'tar' before it.
    assert split_extensions('archive.tar.gz') == ('archive.tar.gz', '')


def test_split_extensions_returns_no_extension_for_a_bare_name():
    assert split_extensions('README') == ('README', '')


def test_split_extensions_treats_an_all_extension_looking_name_as_name_plus_extension():
    assert split_extensions('odt.xlf') == ('odt', 'xlf')


def test_split_extensions_returns_nothing_for_a_single_bare_three_letter_name():
    # A real, non-obvious quirk of this vendored function: a name with no
    # dot that happens to be exactly three letters is entirely consumed
    # as "all extension", then the truncation meant for the multi-part
    # case leaves both halves empty.
    assert split_extensions('abc') == ('', '')


# Project.__init__() / __del__() #

def test_init_creates_a_default_projstore_when_none_given():
    project = Project()

    assert isinstance(project.store, ProjectStore)


def test_init_uses_the_given_projstore():
    store = ProjectStore()

    project = Project(store)

    assert project.store is store


def test_del_removes_the_store_reference_when_one_is_set():
    project = Project(ProjectStore())

    project.__del__()

    assert not hasattr(project, 'store')
    # Real GC will call __del__() again once this local reference itself
    # goes out of scope - restore a valid state so that second call is
    # the safe no-op path, not a crash on the attribute we just removed.
    project.store = None


def test_del_does_nothing_without_a_store():
    project = Project.__new__(Project)
    project.store = None

    project.__del__()  # must not raise


# trivial proxies #

def test_add_source_proxies_to_the_store():
    calls = []
    store = SimpleNamespace(append_sourcefile=lambda afile, fname: calls.append((afile, fname)) or ('fileobj', 'sources/x.po'))
    project = Project(store)

    result = project.add_source('srcfile', 'x.po')

    assert calls == [('srcfile', 'x.po')]
    assert result == ('fileobj', 'sources/x.po')


def test_close_proxies_to_the_store():
    calls = []
    store = SimpleNamespace(close=lambda: calls.append('closed'))
    project = Project(store)

    project.close()

    assert calls == ['closed']


def test_export_file_writes_the_stores_file_contents_to_the_destination(tmp_path):
    store = SimpleNamespace(get_file=lambda fname: BytesIO(b'hello world'))
    project = Project(store)
    dest = tmp_path / 'out.txt'

    project.export_file('some/file.txt', str(dest))

    assert dest.read_bytes() == b'hello world'


def test_get_file_proxies_to_the_store():
    store = SimpleNamespace(get_file=lambda fname: ('handle', fname))
    project = Project(store)

    assert project.get_file('x.po') == ('handle', 'x.po')


def test_get_proj_filename_proxies_to_the_store():
    store = SimpleNamespace(get_proj_filename=lambda realfname: 'sources/' + realfname)
    project = Project(store)

    assert project.get_proj_filename('x.po') == 'sources/x.po'


def test_get_real_filename_prefers_the_name_attribute():
    fileobj = SimpleNamespace(name='/tmp/real.po')
    store = SimpleNamespace(get_file=lambda fname: fileobj)
    project = Project(store)

    assert project.get_real_filename('sources/x.po') == '/tmp/real.po'


def test_get_real_filename_falls_back_to_the_filename_attribute():
    fileobj = SimpleNamespace(filename='archive/real.po')
    store = SimpleNamespace(get_file=lambda fname: fileobj)
    project = Project(store)

    assert project.get_real_filename('sources/x.po') == 'archive/real.po'


def test_get_real_filename_raises_without_either_attribute():
    store = SimpleNamespace(get_file=lambda fname: SimpleNamespace())
    project = Project(store)

    with pytest.raises(ValueError, match='has no real file'):
        project.get_real_filename('sources/x.po')


def test_remove_file_proxies_to_the_store():
    calls = []
    store = SimpleNamespace(remove_file=lambda fname, ftype: calls.append((fname, ftype)))
    project = Project(store)

    project.remove_file('sources/x.po', ftype='src')

    assert calls == [('sources/x.po', 'src')]


def test_save_proxies_to_the_store():
    calls = []
    store = SimpleNamespace(save=lambda filename: calls.append(filename))
    project = Project(store)

    project.save('out.zip')

    assert calls == ['out.zip']


def test_update_file_proxies_to_the_store():
    calls = []
    store = SimpleNamespace(update_file=lambda proj_fname, infile: calls.append((proj_fname, infile)))
    project = Project(store)

    project.update_file('sources/x.po', 'newfile')

    assert calls == [('sources/x.po', 'newfile')]


def test_add_source_convert_adds_then_converts_the_added_source():
    calls = []
    store = SimpleNamespace(
        append_sourcefile=lambda afile, fname: calls.append(('add', afile, fname)) or ('srcfileobj', 'sources/x.odt'))
    project = Project(store)
    project.convert_forward = lambda fname, convert_options=None: calls.append(('convert', fname, convert_options)) or ('transfileobj', 'trans/x.odt.xlf')

    result = project.add_source_convert('srcfile', 'x.odt', convert_options={'opt': 1})

    assert calls == [('add', 'srcfile', 'x.odt'), ('convert', 'sources/x.odt', {'opt': 1})]
    assert result == ('srcfileobj', 'sources/x.odt', 'transfileobj', 'trans/x.odt.xlf')


# Project.convert_forward() - real ProjectStore + real files, with only
# the external translate.convert.factory.convert() call stubbed out #

def _stub_convert(monkeypatch, tmp_path, ext='xlf', content=b'converted', capture=None, created=None):
    def fake_convert(inputfile, template, options, convert_options):
        if capture is not None:
            capture['template'] = template
        out_fd, out_path = tempfile.mkstemp(dir=str(tmp_path), suffix='.tmp')
        os.write(out_fd, content)
        os.close(out_fd)
        if created is not None:
            created.append(out_path)
        return open(out_path, 'rb'), ext
    monkeypatch.setattr(project_module.convert_factory, 'convert', fake_convert)


def test_convert_forward_converts_a_source_file_and_records_the_conversion(tmp_path, monkeypatch):
    _stub_convert(monkeypatch, tmp_path)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))

    outputfile, output_fname = project.convert_forward('sources/greeting.odt')

    assert output_fname == 'trans/greeting.odt.xlf'
    assert outputfile.read() == b'converted'
    assert store.convert_map['sources/greeting.odt'] == ('trans/greeting.odt.xlf', None)
    assert 'trans/greeting.odt.xlf' in store


def test_convert_forward_refuses_to_convert_a_target_document_further(tmp_path, monkeypatch):
    _stub_convert(monkeypatch, tmp_path)
    tgt_path = tmp_path / 'out.odt'
    tgt_path.write_bytes(b'data')
    store = ProjectStore()
    store.append_targetfile(str(tgt_path))
    project = Project(store)

    with pytest.raises(ValueError, match='Cannot convert a target document further'):
        project.convert_forward('targets/out.odt')


def test_convert_forward_derives_the_template_name_from_a_file_objects_name(tmp_path, monkeypatch):
    capture = {}
    _stub_convert(monkeypatch, tmp_path, capture=capture)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    templ_path = tmp_path / 'template.ott'
    templ_path.write_bytes(b'template bytes')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))

    with open(str(templ_path), 'rb') as template_file:
        project.convert_forward('sources/greeting.odt', template=template_file)

    assert store.convert_map['sources/greeting.odt'][1] == str(templ_path)
    assert capture['template'] is template_file


def test_convert_forward_reuses_a_previously_recorded_template(tmp_path, monkeypatch):
    capture = {}
    _stub_convert(monkeypatch, tmp_path, capture=capture)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    templ_path = tmp_path / 'template.ott'
    templ_path.write_bytes(b'template bytes')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))
    store.append_sourcefile(str(templ_path))
    store.convert_map['sources/greeting.odt'] = ('trans/old-output.xlf', 'sources/template.ott')

    project.convert_forward('sources/greeting.odt')

    assert getattr(capture['template'], 'name', None) == str(templ_path)


def test_convert_forward_finds_the_original_source_as_a_template_via_reverse_lookup(tmp_path, monkeypatch):
    capture = {}
    _stub_convert(monkeypatch, tmp_path, capture=capture)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    trans_path = tmp_path / 'greeting.odt.xlf'
    trans_path.write_bytes(b'xliff bytes')
    store = ProjectStore()
    project = Project(store)
    store.append_sourcefile(str(src_path))
    store.append_transfile(str(trans_path))
    store.convert_map['sources/greeting.odt'] = ('trans/greeting.odt.xlf', None)

    project.convert_forward('trans/greeting.odt.xlf')

    assert getattr(capture['template'], 'name', None) == str(src_path)


def test_convert_forward_removes_the_previous_output_before_reconverting(tmp_path, monkeypatch):
    # Also the regression case for re-converting a file whose previous
    # conversion recorded no template (the common case) - that used to
    # crash with FileNotInProjectError from get_file(None).
    _stub_convert(monkeypatch, tmp_path)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    old_output_path = tmp_path / 'old-output.xlf'
    old_output_path.write_bytes(b'stale')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))
    store.append_transfile(str(old_output_path))
    store.convert_map['sources/greeting.odt'] = ('trans/old-output.xlf', None)

    project.convert_forward('sources/greeting.odt')

    assert 'trans/old-output.xlf' not in store


def test_convert_forward_keeps_the_previous_output_when_overwrite_is_disabled(tmp_path, monkeypatch):
    _stub_convert(monkeypatch, tmp_path)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    old_output_path = tmp_path / 'old-output.xlf'
    old_output_path.write_bytes(b'stale')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))
    store.append_transfile(str(old_output_path))
    store.convert_map['sources/greeting.odt'] = ('trans/old-output.xlf', None)

    project.convert_forward('sources/greeting.odt', overwrite_output=False)

    assert 'trans/old-output.xlf' in store


def test_convert_forward_applies_an_output_suffix(tmp_path, monkeypatch):
    _stub_convert(monkeypatch, tmp_path)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))

    _outputfile, output_fname = project.convert_forward('sources/greeting.odt', output_suffix='-translated')

    assert output_fname == 'trans/greeting-translated.odt.xlf'


def test_convert_forward_collapses_a_redundant_double_extension(tmp_path, monkeypatch):
    _stub_convert(monkeypatch, tmp_path, ext='odt')
    trans_path = tmp_path / 'doc.odt.xlf'
    trans_path.write_bytes(b'xliff bytes')
    store = ProjectStore()
    project = Project(store)
    store.append_transfile(str(trans_path))

    _outputfile, output_fname = project.convert_forward('trans/doc.odt.xlf')

    assert output_fname == 'targets/doc.odt'


def test_convert_forward_falls_back_to_the_current_directory_without_a_real_input_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_convert(monkeypatch, tmp_path)
    store = ProjectStore()
    project = Project(store)
    store.append_sourcefile(BytesIO(b'source bytes'), fname='greeting.odt')

    _outputfile, output_fname = project.convert_forward('sources/greeting.odt')

    assert output_fname == 'trans/greeting.odt.xlf'


def test_convert_forward_raises_and_cleans_up_when_the_output_already_exists(tmp_path, monkeypatch):
    created = []
    _stub_convert(monkeypatch, tmp_path, created=created)
    src_path = tmp_path / 'greeting.odt'
    src_path.write_bytes(b'source bytes')
    existing_output = tmp_path / 'greeting.odt.xlf'
    existing_output.write_bytes(b'already here')
    store = ProjectStore()
    project = Project(store)
    project.add_source(str(src_path))

    with pytest.raises(OSError, match='Output file already exists'):
        project.convert_forward('sources/greeting.odt')

    assert not os.path.exists(created[0])
    assert existing_output.read_bytes() == b'already here'
