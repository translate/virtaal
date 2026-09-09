#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util

__all__ = ['check_dependencies', 'extra_tests', 'import_checks']


# Modules to try and import:
import_checks = ['translate', 'gtk', 'lxml.etree', 'json', 'pycurl', 'sqlite3', 'wsgiref', 'diff_match_patch']


#########################
# Specific Module Tests #
#########################
MIN_GTK_VERSION = (3, 0, 0)
def test_gtk_version():
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        return not Gtk.check_version(*MIN_GTK_VERSION)
        # GtkBuilder was in GTK+ earlier already, but at least this bug is
        # quite nasty:
        # https://bugzilla.gnome.org/show_bug.cgi?id=582025
        # That seems to be fixed in time for 2.18 which was released in
        # September 2009
    except Exception:
        pass
    return False

def test_sqlite3_version():
    #TODO: work out if we need certain versions
    return importlib.util.find_spec('sqlite3.dbapi2') is not None

def test_json():
    # We can work with simplejson or json (available since Python 2.6)
    return importlib.util.find_spec('simplejson') is not None or importlib.util.find_spec('json') is not None

MIN_TRANSLATE_VERSION = (1, 9, 0)
def test_translate_toolkit_version():
    try:
        from translate.__version__ import ver
        return ver >= MIN_TRANSLATE_VERSION
    except Exception:
        pass
    return False


extra_tests = {
    'gtk': test_gtk_version,
    'sqlite3': test_sqlite3_version,
    'translate': test_translate_toolkit_version,
    'json': test_json,
}


#############################
# General Testing Functions #
#############################
def test_import(modname):
    try:
        __import__(modname, {}, {}, [])
    except ImportError:
        return False
    return True

def check_dependencies(module_names=import_checks):
    """Returns a list of modules that could not be imported."""
    names = []
    for name in module_names:
        if name in extra_tests:
            if not extra_tests[name]():
                names.append(name)
        elif not test_import(name):
            names.append(name)
    return names



########
# MAIN #
########
if __name__ == '__main__':
    failed = check_dependencies()
    if not failed:
        print('All dependencies met.')
    else:
        print('Dependencies not met: %s' % (', '.join(failed)))
