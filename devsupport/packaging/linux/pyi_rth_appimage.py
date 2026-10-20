#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

# PyInstaller runtime hook for the Linux AppImage: point GTK at the
# bundled input method modules (and IBus's, under Wayland) and pyenchant
# at the bundled enchant.
# The bundle is mounted at a new path on every run, so the input method
# cache (absolute paths, written by virtaal.spec with a placeholder)
# is rewritten here, the way PyInstaller's GdkPixbuf hook does its own.


def _setup():
    import atexit
    import os
    import shutil
    import sys
    import tempfile

    bundle = sys._MEIPASS

    template = os.path.join(bundle, 'lib', 'gtk-3.0', '3.0.0', 'immodules.cache.in')
    if os.path.isfile(template) and 'GTK_IM_MODULE_FILE' not in os.environ:
        with open(template, encoding='utf-8') as f:
            cache = f.read().replace('@BUNDLE@', bundle)
        cache_dir = tempfile.mkdtemp(prefix='virtaal-gtk-')
        atexit.register(shutil.rmtree, cache_dir, ignore_errors=True)
        cache_file = os.path.join(cache_dir, 'immodules.cache')
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(cache)
        os.environ['GTK_IM_MODULE_FILE'] = cache_file

    # Under Wayland, this GTK's own input method module (3.24.33) makes
    # the IBus candidate window and the text being typed jump about; its
    # IBus module doesn't. Only when IBus is the desktop's input method
    # and nothing else was chosen. helperprocess.host_env() drops it again.
    if (os.environ.get('WAYLAND_DISPLAY') and 'GTK_IM_MODULE' not in os.environ
            and '@im=ibus' in os.environ.get('XMODIFIERS', '')):
        os.environ['GTK_IM_MODULE'] = 'ibus'
        os.environ['_VIRTAAL_SET_GTK_IM_MODULE'] = '1'

    # pyenchant sets enchant's prefix to this path's grandparent, where
    # the bundled providers are (enchant/lib/enchant-2/).
    os.environ.setdefault('PYENCHANT_LIBRARY_PATH', os.path.join(bundle, 'enchant', 'lib', 'libenchant-2.so.2'))


_setup()
del _setup
