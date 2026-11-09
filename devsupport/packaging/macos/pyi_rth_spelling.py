#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

# PyInstaller runtime hook for the macOS .app: point pyenchant at the
# bundled enchant, the library GtkSpell links, before anything loads
# enchant. pyenchant gives enchant the path's grandparent,
# Frameworks/libenchant, as its prefix: the bundled providers and
# enchant.ordering are in its lib/enchant-2/ and share/enchant-2/.


def _setup():
    import os
    import sys

    bundle = sys._MEIPASS
    os.environ['PYENCHANT_LIBRARY_PATH'] = os.path.join(bundle, 'libenchant', os.pardir, 'libenchant-2.2.dylib')
    os.environ['_VIRTAAL_BUNDLED_SPELLING'] = '1'


_setup()
del _setup
