#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import io

import pytest

from virtaal.support.projstore import (
    FileExistsInProjectError,
    FileNotInProjectError,
    ProjectStore,
)


class _FnameOnly:
    """A file-like stand-in with only a .filename attribute, not .name -
    exercises append_file()/get_file()'s second-choice lookup."""
    def __init__(self, filename):
        self.filename = filename


# sourcefiles/targetfiles/transfiles properties, __contains__ #

def test_sourcefiles_targetfiles_transfiles_properties_reflect_appended_files():
    store = ProjectStore()
    store.append_sourcefile(io.BytesIO(b"s"), "in.po")
    store.append_targetfile(io.BytesIO(b"t"), "out.po")
    store.append_transfile(io.BytesIO(b"x"), "mid.po")

    assert store.sourcefiles == ("sources/in.po",)
    assert store.targetfiles == ("targets/out.po",)
    assert store.transfiles == ("trans/mid.po",)


def test_contains_checks_both_names_and_the_stored_file_object():
    store = ProjectStore()
    afile = io.BytesIO(b"x")
    _afile, fname = store.append_file(afile, "check.po", ftype="src")

    assert fname in store
    assert afile in store
    assert "missing.po" not in store


# append_file() #

def test_append_file_rejects_an_unknown_ftype():
    store = ProjectStore()

    with pytest.raises(ValueError, match="Invalid file type"):
        store.append_file(io.BytesIO(b"x"), "note.po", ftype="bogus")


def test_append_file_derives_realfname_from_a_filename_attribute(tmp_path):
    src = tmp_path / "glossary.tbx"
    src.write_bytes(b"data")
    store = ProjectStore()
    afile = _FnameOnly(str(src))

    store.append_file(afile, "glossary.tbx", ftype="src")

    assert store._files["sources/glossary.tbx"] == str(src)


def test_append_file_leaves_realfname_unresolved_when_nothing_points_at_a_real_file():
    store = ProjectStore()
    afile = io.BytesIO(b"data")

    _afile, fname = store.append_file(afile, "note.txt", ftype="src")

    assert store._files[fname] is afile


def test_append_file_derives_fname_from_a_name_attribute(tmp_path):
    src = tmp_path / "report.txt"
    src.write_bytes(b"data")
    store = ProjectStore()
    with open(src, "rb") as fh:
        _afile, fname = store.append_file(fh, None, ftype="src")

    assert fname == "sources/report.txt"


def test_append_file_derives_fname_from_a_filename_attribute():
    store = ProjectStore()
    afile = _FnameOnly("legacy_report.txt")

    _afile, fname = store.append_file(afile, None, ftype="trans")

    assert fname == "trans/legacy_report.txt"


def test_append_file_rejects_a_duplicate_filename():
    store = ProjectStore()
    store.append_file(io.BytesIO(b"a"), "dup.po", ftype="src")

    with pytest.raises(FileExistsInProjectError):
        store.append_file(io.BytesIO(b"b"), "dup.po", ftype="src")


def test_append_targetfile_and_transfile_delegate_with_the_right_ftype():
    store = ProjectStore()
    _afile, tgt_fname = store.append_targetfile(io.BytesIO(b"t"), "out.po")
    _afile, trans_fname = store.append_transfile(io.BytesIO(b"x"), "mid.po")

    assert tgt_fname == "targets/out.po"
    assert trans_fname == "trans/mid.po"


# remove_file() #

def test_remove_file_raises_for_an_unknown_filename():
    store = ProjectStore()

    with pytest.raises(FileNotInProjectError):
        store.remove_file("nope.po")


def test_remove_file_closes_a_stored_handle_and_forgets_it():
    # append_file() only stores the file *object* itself when it can't
    # resolve a real on-disk path for it - a plain BytesIO, here.
    store = ProjectStore()
    afile = io.BytesIO(b"data")
    _afile, fname = store.append_file(afile, "in.po", ftype="src")
    assert not afile.closed

    store.remove_file(fname)

    assert afile.closed
    assert fname not in store._files
    assert fname not in store.sourcefiles


def test_remove_sourcefile_targetfile_transfile_delegate_with_the_right_ftype():
    store = ProjectStore()
    _afile, src_fname = store.append_sourcefile(io.BytesIO(b"s"), "a.po")
    _afile, tgt_fname = store.append_targetfile(io.BytesIO(b"t"), "b.po")
    _afile, trans_fname = store.append_transfile(io.BytesIO(b"x"), "c.po")

    store.remove_sourcefile(src_fname)
    store.remove_targetfile(tgt_fname)
    store.remove_transfile(trans_fname)

    assert store.sourcefiles == store.targetfiles == store.transfiles == ()


# cleanup() #

def test_cleanup_closes_every_stored_handle():
    store = ProjectStore()
    afile = io.BytesIO(b"data")
    store.append_file(afile, "in.po", ftype="src")

    store.cleanup()

    assert afile.closed


# get_file() #

def test_get_file_raises_for_an_unknown_filename():
    store = ProjectStore()

    with pytest.raises(FileNotInProjectError):
        store.get_file("nope.po")


def test_get_file_opens_a_path_string_fresh():
    store = ProjectStore()
    store._files["note.po"] = __file__  # a real path on disk

    result = store.get_file("note.po")

    assert result.mode == "rb"
    result.close()


def test_get_file_returns_a_still_open_object_unchanged():
    store = ProjectStore()
    afile = io.BytesIO(b"data")
    _afile, fname = store.append_file(afile, "note.po", ftype="src")

    assert store.get_file(fname) is afile


def test_get_file_reopens_via_the_project_filename_when_it_is_itself_a_real_path(tmp_path):
    real_path = tmp_path / "note.po"
    real_path.write_bytes(b"reopened contents")
    store = ProjectStore()
    closed = io.BytesIO(b"stale")
    closed.close()
    store._files[str(real_path)] = closed

    result = store.get_file(str(real_path))

    assert result.read() == b"reopened contents"


def test_get_file_reopens_via_a_name_attribute(tmp_path):
    real_path = tmp_path / "note.po"
    real_path.write_bytes(b"reopened contents")
    store = ProjectStore()
    closed = io.BytesIO(b"stale")
    closed.name = str(real_path)
    closed.close()
    store._files["note.po"] = closed

    result = store.get_file("note.po")

    assert result.read() == b"reopened contents"


def test_get_file_reopens_via_a_filename_attribute_when_name_is_unusable(tmp_path):
    real_path = tmp_path / "note.po"
    real_path.write_bytes(b"reopened contents")
    store = ProjectStore()
    closed = _FnameOnly(str(real_path))
    closed.closed = True
    store._files["note.po"] = closed

    result = store.get_file("note.po")

    assert result.read() == b"reopened contents"


def test_get_file_raises_oserror_when_nothing_can_locate_the_file():
    # Used to crash with TypeError instead of reaching this OSError.
    store = ProjectStore()
    closed = io.BytesIO(b"stale")
    closed.close()
    store._files["gone.po"] = closed

    with pytest.raises(OSError):
        store.get_file("gone.po")


# get_filename_type() #

def test_get_filename_type_finds_the_owning_list():
    store = ProjectStore()
    _afile, fname = store.append_file(io.BytesIO(b"x"), "note.po", ftype="tgt")

    assert store.get_filename_type(fname) == "tgt"


def test_get_filename_type_raises_for_an_unknown_filename():
    store = ProjectStore()

    with pytest.raises(FileNotInProjectError):
        store.get_filename_type("nope.po")


# get_proj_filename() #

def test_get_proj_filename_finds_by_key_or_stored_value(tmp_path):
    src = tmp_path / "in.po"
    src.write_bytes(b"data")
    store = ProjectStore()
    _afile, fname = store.append_file(str(src), None, ftype="src")

    assert store.get_proj_filename(str(src)) == fname
    assert store.get_proj_filename(fname) == fname


def test_get_proj_filename_raises_for_an_unknown_real_filename():
    store = ProjectStore()

    with pytest.raises(ValueError):
        store.get_proj_filename("/no/such/file")


# update_file() #

def test_update_file_replaces_the_content_under_the_same_project_name():
    store = ProjectStore()
    _afile, fname = store.append_file(io.BytesIO(b"old"), "note.po", ftype="src")

    new_afile = io.BytesIO(b"new")
    store.update_file(fname, new_afile)

    assert store._files[fname] is new_afile
    assert store.get_filename_type(fname) == "src"
    assert store.sourcefiles.count(fname) == 1


# _generate_settings() #

def test_generate_settings_includes_target_files():
    store = ProjectStore()
    store.append_file(io.BytesIO(b"t"), "out.po", ftype="tgt")

    xml = store._generate_settings()

    assert b"<targets>" in xml
    assert b"targets/out.po" in xml


def test_generate_settings_includes_conversions_with_and_without_a_template():
    store = ProjectStore()
    store.append_file(io.BytesIO(b"s"), "doc.odt", ftype="src")
    store.append_file(io.BytesIO(b"x"), "doc.odt.xlf", ftype="trans")
    store.append_file(io.BytesIO(b"t"), "doc.odt", ftype="tgt")
    store.convert_map = {
        "sources/doc.odt": ("trans/doc.odt.xlf", None),
        "trans/doc.odt.xlf": ("targets/doc.odt", "sources/doc.odt"),
    }

    xml = store._generate_settings()

    assert xml.count(b"<conv>") == 2
    assert b"<template>sources/doc.odt</template>" in xml


def test_generate_settings_skips_a_conversion_referencing_a_removed_file():
    store = ProjectStore()
    store.convert_map = {"sources/gone.odt": ("trans/gone.odt.xlf", None)}

    xml = store._generate_settings()

    assert b"<conv>" not in xml


def test_generate_settings_includes_options():
    store = ProjectStore()
    store.settings["options"] = {"mode": "strict"}

    xml = store._generate_settings()

    assert b'<option name="mode">strict</option>' in xml


# _load_settings() #

def test_load_settings_round_trips_files_and_conversions_with_a_template():
    store = ProjectStore()
    store.append_file(io.BytesIO(b"s"), "doc.odt", ftype="src")
    store.append_file(io.BytesIO(b"x"), "doc.odt.xlf", ftype="trans")
    store.append_file(io.BytesIO(b"t"), "doc.odt", ftype="tgt")
    store.convert_map = {
        "sources/doc.odt": ("trans/doc.odt.xlf", None),
        "trans/doc.odt.xlf": ("targets/doc.odt", "sources/doc.odt"),
    }
    xml = store._generate_settings()

    fresh = ProjectStore()
    fresh._load_settings(xml)

    assert fresh.settings["sources"] == ["sources/doc.odt"]
    assert fresh.convert_map == store.convert_map


def test_load_settings_skips_a_conversion_whose_files_are_not_in_the_settings():
    xml = (
        b"<translationproject><conversions><conv>"
        b"<input>sources/missing.odt</input>"
        b"<output>trans/missing.odt.xlf</output>"
        b"</conv></conversions></translationproject>"
    )
    store = ProjectStore()

    store._load_settings(xml)

    assert store.convert_map == {}


def test_load_settings_parses_options():
    xml = (
        b"<translationproject><options>"
        b'<option name="mode">strict</option>'
        b"</options></translationproject>"
    )
    store = ProjectStore()

    store._load_settings(xml)

    assert store.settings["options"] == {"mode": "strict"}
