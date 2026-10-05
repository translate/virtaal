#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from translate.storage import base, factory, pypo

POT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "po", "virtaal.pot")


def _format_names():
    """translate-toolkit's name for every format its factory opens, as
        far as each one's optional dependencies are installed."""
    names = {base.TranslationStore.Name}
    for module, cls in factory._classes_str.values():
        try:
            names.add(factory.import_class(module, cls, "translate.storage").Name)
        except ImportError:
            pass
    return names


def test_every_file_format_name_is_translatable():
    # Shown in the Open dialog and Properties; a toolkit upgrade adding a
    # format needs its name in devsupport/tmp_strings.py.
    with open(POT, "rb") as f:
        msgids = {str(unit.source) for unit in pypo.pofile(f).units}

    assert sorted(_format_names() - msgids) == []
