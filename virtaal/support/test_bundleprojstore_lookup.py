#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""BundleProjectStore's file lookup and its errors, on real bundles."""

import io
import os
import sys
from zipfile import ZipFile

import pytest

from virtaal.support.bundleprojstore import BundleProjectStore
from virtaal.support.projstore import FileNotInProjectError

PO = b'msgid "Open"\nmsgstr ""\n'


@pytest.fixture
def bundle(tmp_path):
    store = BundleProjectStore(str(tmp_path / 'bundle.zip'))
    yield store
    store.close()


def _append(bundle, tmp_path, name='open.po', content=PO, **kwargs):
    path = tmp_path / name
    path.write_bytes(content)
    afile, pfname = bundle.append_file(str(path), None, 'trans', **kwargs)
    afile.close()
    return path, pfname


def _zip_names(bundle):
    return bundle.zip.namelist()


def test_a_file_already_in_the_bundle_cannot_be_added_again(bundle, tmp_path):
    _append(bundle, tmp_path)

    with pytest.raises(ValueError, match='File already in bundle archive: trans/open.po'):
        bundle.append_transfile(io.BytesIO(PO), 'trans/open.po')


def test_a_file_named_by_its_place_in_the_archive_cannot_be_added_again(bundle, tmp_path):
    _append(bundle, tmp_path)

    with pytest.raises(ValueError, match='File already in bundle archive: trans/open.po'):
        bundle.append_file('trans/open.po', None)


# The original stays open (#4457), and Windows can't remove an open file.
@pytest.mark.skipif(sys.platform == 'win32', reason='the original is still open there (#4457)')
def test_appending_with_delete_orig_removes_the_original(bundle, tmp_path):
    path, pfname = _append(bundle, tmp_path, delete_orig=True)

    assert not path.exists()
    with bundle.get_file(pfname) as stored:
        assert stored.read() == PO


def test_appending_its_own_extracted_file_with_delete_orig_keeps_it(bundle, tmp_path):
    _, pfname = _append(bundle, tmp_path)
    with bundle.get_file(pfname) as extracted:
        afile, _ = bundle.append_file(extracted, 'trans/copy.po', delete_orig=True)
    afile.close()

    assert os.path.isfile(extracted.name)


def test_getting_a_file_not_in_the_bundle_fails(bundle):
    with pytest.raises(FileNotInProjectError):
        bundle.get_file('trans/missing.po')


def test_a_project_file_name_is_its_own_project_name(bundle, tmp_path):
    _, pfname = _append(bundle, tmp_path)

    assert bundle.get_proj_filename(pfname) == pfname


def test_an_extracted_file_gives_the_project_name_it_came_from(bundle, tmp_path):
    # What the store controller looks up for a file opened from a bundle.
    _, pfname = _append(bundle, tmp_path)
    with bundle.get_file(pfname) as extracted:
        realfname = extracted.name

    assert realfname != pfname
    assert bundle.get_proj_filename(realfname) == pfname


def test_a_file_outside_the_bundle_has_no_project_name(bundle, tmp_path):
    outside = str(tmp_path / 'elsewhere.po')

    with pytest.raises(ValueError, match='Real file not in project store'):
        bundle.get_proj_filename(outside)


def test_updating_a_file_not_in_the_project_fails(bundle):
    with pytest.raises(FileNotInProjectError):
        bundle.update_file('trans/missing.po', io.BytesIO(PO))


def test_updating_a_file_replaces_it_in_the_archive(bundle, tmp_path):
    _, pfname = _append(bundle, tmp_path)

    bundle.update_file(pfname, io.BytesIO(b'msgid "Save"\nmsgstr ""\n'))

    assert bundle.zip.read(pfname) == b'msgid "Save"\nmsgstr ""\n'
    assert _zip_names(bundle).count(pfname) == 1


def test_updating_a_project_file_missing_from_the_archive_adds_it(tmp_path):
    # A bundle whose project.xtp lists a file its archive lacks.
    good = BundleProjectStore(str(tmp_path / 'good.zip'))
    _append(good, tmp_path)
    good.close()
    with ZipFile(tmp_path / 'good.zip') as source, ZipFile(tmp_path / 'broken.zip', 'w') as broken:
        broken.writestr('project.xtp', source.read('project.xtp'))
    bundle = BundleProjectStore(str(tmp_path / 'broken.zip'))
    try:
        assert 'trans/open.po' not in bundle.zip.namelist()

        bundle.update_file('trans/open.po', io.BytesIO(PO))

        assert bundle.zip.read('trans/open.po') == PO
    finally:
        bundle.close()


def test_zip_delete_wants_a_list_of_names(bundle):
    with pytest.raises(TypeError, match='fnames must be list or tuple'):
        bundle._zip_delete('trans/open.po')


def test_zip_delete_needs_an_open_archive(bundle):
    archive, bundle.zip = bundle.zip, None
    try:
        with pytest.raises(ValueError, match='No zip file to work on'):
            bundle._zip_delete(['trans/open.po'])
    finally:
        bundle.zip = archive


def test_zip_delete_of_a_name_not_in_the_archive_changes_nothing(bundle, tmp_path):
    _, pfname = _append(bundle, tmp_path)
    before = _zip_names(bundle)

    with pytest.raises(KeyError, match='File not in zip archive: trans/missing.po'):
        bundle._zip_delete([pfname, 'trans/missing.po'])

    assert _zip_names(bundle) == before
