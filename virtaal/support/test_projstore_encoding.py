#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regression tests for #3609: projstore.py/bundleprojstore.py open a
project file in binary mode."""

from virtaal.support.bundleprojstore import BundleProjectStore
from virtaal.support.projstore import ProjectStore

NON_ASCII_PO = (
    'msgid ""\n'
    'msgstr ""\n'
    '"Content-Type: text/plain; charset=UTF-8\\n"\n'
    "\n"
    'msgid "coffee"\n'
    'msgstr "café ☕"\n'
).encode()


def test_append_file_opens_a_string_path_in_binary_mode(tmp_path):
    src = tmp_path / "source.po"
    src.write_bytes(NON_ASCII_PO)

    store = ProjectStore()
    afile, _fname = store.append_file(str(src), None, ftype="src")

    assert afile.mode == "rb"
    assert afile.read() == NON_ASCII_PO


def test_update_from_tempfiles_opens_tempfiles_in_binary_mode(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.zip"
    tempfname = tmp_path / "trans_source.po"
    tempfname.write_bytes(NON_ASCII_PO)

    bundle = BundleProjectStore(str(bundle_path))
    try:
        # Seed the state _update_from_tempfiles() expects (a project file
        # already in the zip, with a pending temp-file update) directly,
        # rather than via append_file() - which this doesn't need.
        bundle.zip.writestr("trans/source.po", b"placeholder")
        bundle._files["trans/source.po"] = None
        bundle._transfiles.append("trans/source.po")
        bundle._tempfiles = {str(tempfname): "trans/source.po"}

        opened_modes = []
        real_open = open

        def spying_open(file, mode="r", *args, **kwargs):
            if str(file) == str(tempfname):
                opened_modes.append(mode)
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", spying_open)

        bundle._update_from_tempfiles()

        assert opened_modes == ["rb"]
        # On a UTF-8-locale host (Linux/macOS) content still round-trips
        # even opened as text - the mode assertion above is what actually
        # catches this on a cp1252-locale host (Windows).
        assert bundle.zip.read("trans/source.po") == NON_ASCII_PO
    finally:
        bundle._tempfiles = {}
        bundle.close()
