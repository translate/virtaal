#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Trims Babel's locale data in a frozen build to what Virtaal's UI
languages load. PyInstaller's own Babel hook bundles every locale."""

import glob
import os
from pathlib import Path

from babel import localedata


def ui_locale_names(po_dir):
    """The Babel locale data files (without .dat) that formatting
        numbers loads for each UI language in po_dir, parents included."""
    from virtaal.support.libi18n.numbers import ui_locale

    loaded = set()
    load = localedata.load

    def recording_load(name, merge_inherited=True):
        loaded.add(name)
        return load(name, merge_inherited)

    localedata._cache.clear()
    localedata.load = recording_load
    try:
        for path in glob.glob(os.path.join(po_dir, "*.po")):
            locale = ui_locale(os.path.basename(path)[:-len(".po")])
            locale.decimal_formats, locale.percent_formats, locale.default_numbering_system
    finally:
        localedata.load = load
        localedata._cache.clear()
    return loaded | {"root"}


def trim(datas, po_dir):
    """PyInstaller datas without the Babel locale files no UI language
        loads."""
    keep = ui_locale_names(po_dir)
    trimmed = []
    for entry in datas:
        dest = Path(entry[0])
        if dest.parts[:2] == ("babel", "locale-data") and dest.suffix == ".dat" and dest.stem not in keep:
            continue
        trimmed.append(entry)
    return trimmed
