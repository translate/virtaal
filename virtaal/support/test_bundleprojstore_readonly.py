#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""A bundle that can't be written to opens read-only (#4713)."""

import io
import os
from zipfile import ZipFile

import pytest

from virtaal.support import bundleprojstore
from virtaal.support.project import Project

PO = b'msgid "cat"\nmsgstr "kat"\n'


@pytest.fixture
def read_only_bundle(tmp_path, monkeypatch):
    """A bundle with one translation file, that os.access() says can't
    be written to (chmod alone doesn't stop root), and its bytes."""
    path = str(tmp_path / 'project.zip')
    bundle = bundleprojstore.BundleProjectStore(path)
    bundle.append_file(io.BytesIO(PO), 'trans/af.po', ftype='trans')
    bundle.save()
    bundle.close()
    real_access = os.access
    monkeypatch.setattr(
        bundleprojstore.os,
        'access',
        lambda name, mode: False if name == path else real_access(name, mode),
    )
    with open(path, 'rb') as f:
        return path, f.read()


def _po_in(path):
    with ZipFile(path) as archive:
        return archive.read('trans/af.po')


def test_a_read_only_bundle_opens(read_only_bundle):
    path, _data = read_only_bundle

    project = Project(bundleprojstore.BundleProjectStore(path))
    try:
        assert project.store.read_only
        with project.get_file('trans/af.po') as transfile:
            assert transfile.read() == PO
    finally:
        project.close()


def test_saving_a_read_only_bundle_needs_another_name(read_only_bundle, tmp_path):
    path, data = read_only_bundle
    project = Project(bundleprojstore.BundleProjectStore(path))
    try:
        # What StoreController.save_file() does.
        with project.get_file('trans/af.po') as transfile:
            real_filename = transfile.name
        with open(real_filename, 'wb') as f:
            f.write(PO.replace(b'kat', b'katjie'))
        with open(real_filename, 'rb') as infile:
            project.update_file('trans/af.po', infile)

        with pytest.raises(PermissionError):
            project.save()
        copy = str(tmp_path / 'copy.zip')
        project.save(copy)

        assert _po_in(copy) == PO.replace(b'kat', b'katjie')
        assert not project.store.read_only
    finally:
        project.close()
    with open(path, 'rb') as f:
        assert f.read() == data


def test_a_new_file_in_a_read_only_bundle_is_kept_for_save_as(read_only_bundle, tmp_path):
    path, data = read_only_bundle
    store = bundleprojstore.BundleProjectStore(path)
    try:
        store.append_file(io.BytesIO(b'new'), 'targets/af.txt', ftype='tgt')
        copy = str(tmp_path / 'copy.zip')
        store.save(copy)

        with ZipFile(copy) as archive:
            assert archive.read('targets/af.txt') == b'new'
    finally:
        store.close()
    with open(path, 'rb') as f:
        assert f.read() == data
