#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2011 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""This provides access to the native file dialogs for certain platforms, and
some related helper code."""

import os
import sys
import gettext

from virtaal.common import pan_app

#TODO:
# - refactor repeated parts
# - Confirm overwrite works correctly everywhere
# - Confirm error handling works correctly


def _dialog_to_use():
    # We want to know if we should use a native dialog, but don't want to show
    # it in a different language than the Virtaal UI. So we can try to detect
    # if the system (Windows/KDE) is in the same language as the Virtaal GUI.
    ui_language = pan_app.ui_language

    if sys.platform == 'win32':
        from virtaal.support.libi18n.locale import get_win32_system_lang
        win32_lang = get_win32_system_lang()
        if win32_lang == ui_language or ui_language == 'en' and win32_lang == 'C':
            return 'win32'

    elif os.environ.get('KDE_FULL_SESSION') == 'true' and ( \
                pan_app.ui_language == 'en' or \
                gettext.dgettext('kdelibs4', '') or \
                not gettext.dgettext('gtk20', '')):
            return 'kdialog'

    return None # default

# Hardcode for testing:
dialog_to_use = _dialog_to_use()
#dialog_to_use = 'kdialog'
#dialog_to_use = 'win32'
#dialog_to_use = None

_file_types = []

def _get_file_types():
    global _file_types
    if _file_types:
        return _file_types
    from translate.storage import factory
    from locale import strcoll
    all_supported_ext = []
    supported_files = []
    _sorted = sorted(factory.supported_files(), cmp=strcoll, key=lambda x: x[0])
    for name, extensions, mimetypes in _sorted:
        name = _(name)
        extension_filter = ["*.%s" % ext for ext in extensions]
        all_supported_ext.extend(extension_filter)
        supported_files.append((name, extension_filter))

    supported_files.insert(0, (_("All Supported Files"), all_supported_ext))
    _file_types = supported_files
    return supported_files

def _get_used_filetypes(current_filename):
    directory, filename = os.path.split(current_filename)
    name, extension = os.path.splitext(filename)
    supported_files = []
    for type_name, extensions in _get_file_types():
        if "*%s" % extension in extensions:
            supported_files = [(type_name, extensions)]
    return supported_files

### KDE/kdialog ###

def _show_kdialog(window, title, args):
    xid = window.window.xid
    import subprocess
    command = [
            'kdialog',
#            '--name', _('Virtaal'),
#            '--title', 'Virtaal',
            '--caption', _('Virtaal'),
            '--icon', 'virtaal',
            '--title', title,
            '--attach', str(xid),
    ]
    command.extend(args)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    output = output [:-1] # we don't want the last newline
    error = output [:-1] # we don't want the last newline
    ret = process.returncode
    if ret == 0: # success
        filename = output.decode('utf-8') # get system locale
        pan_app.settings.general["lastdir"] = os.path.dirname(filename)
        return filename
    if ret == 1: # cancel
        return u''
    raise Exception("Something went wrong with kdialog", error)


def kdialog_open_dialog(window, title, directory):
    supported_files = _get_file_types()
    args = [
        '--getopenfilename', directory or '.',
        #'''*.po *.xlf|All Translatable Files\n*.ts|Qt .ts file''',   # example with wildcards
        #'text/x-gettext-translation application/x-xliff application/x-linguist,   #example with mime-types
        '\n'.join('|'.join([' '.join(extensions), name]) for name, extensions in supported_files)
    ]
    title = title or _("Choose a Translation File")
    filename = _show_kdialog(window, title, args)
    if filename:
        return (filename, u"file://%s" % filename)
    else:
        return ()

def kdialog_save_dialog(window, title, current_filename):
    supported_files = _get_used_filetypes(current_filename)
    args = [
        '--getsavefilename', current_filename or '.',
        '\n'.join('|'.join([' '.join(extensions), name]) for name, extensions in supported_files)
    ]
    title = title or _("Save")
    return _show_kdialog(window, title, args)


#### Windows/win32 ####

def win32_open_dialog(title, directory):
    # http://msdn.microsoft.com/en-us/library/aa155724%28v=office.10%29.aspx
    import win32gui
    import win32con
    import pywintypes
    supported_files = [ (_(name), ';'.join(extensions)) for name, extensions in _get_file_types() ]

    type_filter = '\0'.join(('%s\0%s') % (name, extensions) for name, extensions in supported_files) + '\0'
    custom_filter = _("All Files") + '\0*.*\0'
    title = title or _('Choose a Translation File')
    try:
        filename, customfilter, flags = win32gui.GetOpenFileNameW(
            InitialDir=directory,
            Flags=win32con.OFN_EXPLORER|win32con.OFN_FILEMUSTEXIST|win32con.OFN_HIDEREADONLY,
            File='', DefExt='',
            Title=title,
            Filter=type_filter,
            CustomFilter=custom_filter,
            FilterIndex=1,              # Select the "All Supported Files"
        )
    except pywintypes.error, e:
        if isinstance(e.args, tuple) and len(e.args) == 3:
            if e.args[0] == 0:
                # cancel
                return ()
        raise Exception("Something went wrong with win32gui", e)
    # success
    pan_app.settings.general["lastdir"] = os.path.dirname(filename)
    return (filename, u"file:///%s" % filename)

def win32_save_dialog(title, current_filename):
    import win32gui
    import win32con
    import pywintypes
    supported_files = _get_used_filetypes(current_filename)

    type_filter = '\0'.join(('%s\0%s') % (name, ';'.join(extensions)) for name, extensions in supported_files) + '\0'
    custom_filter = _("All Files") + '\0*.*\0'
    directory, filename = os.path.split(current_filename)
    name, extension = os.path.splitext(filename)
    title = title or _('Save')
    try:
        filename, customfilter, flags = win32gui.GetSaveFileNameW(
            InitialDir=directory,
            Flags=win32con.OFN_EXPLORER|win32con.OFN_OVERWRITEPROMPT,
            File=name, DefExt=extension,
            Title=title,
            Filter=type_filter,
            CustomFilter=custom_filter,
            FilterIndex=1,              # Select the relevant filter
        )
    except pywintypes.error, e:
        if isinstance(e.args, tuple) and len(e.args) == 3:
            if e.args[0] == 0:
                # cancel
                return u''
        raise Exception("Something went wrong with win32gui", e)
    # success
    return filename
