#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

# PyInstaller runtime hook for the Windows bundle: GtkSpell links the
# enchant in pyenchant's wheel, which pyenchant itself puts on PATH only
# once something imports it.


def _setup():
    import os
    import sys

    enchant_bin = os.path.join(sys._MEIPASS, 'enchant', 'data', 'mingw64', 'bin')
    os.environ['PATH'] = enchant_bin + os.pathsep + os.environ.get('PATH', '')
    os.environ['_VIRTAAL_BUNDLED_SPELLING'] = '1'


_setup()
del _setup
