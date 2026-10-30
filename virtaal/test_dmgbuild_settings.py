#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import runpy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SETTINGS = REPO / 'devsupport' / 'packaging' / 'macos' / 'dmgbuild-settings.py'


def test_the_volume_icon_is_set_under_the_name_dmgbuild_reads():
    # dmgbuild ignores names it doesn't know: volume_icon left every .dmg
    # with the generic drive icon (#4583).
    settings = runpy.run_path(str(SETTINGS))

    assert 'volume_icon' not in settings
    assert (REPO / settings['icon']).is_file()
