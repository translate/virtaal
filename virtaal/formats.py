#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from os import path

import gtk

from translate.storage import factory
import pan_app
from pan_app import _

supported_types = [
    (_("Gettext PO files"), ("*.po", "*.pot"), ("text/x-gettext-translation", "text/x-gettext-translation-template", "application/x-gettext",
"application/x-gettext-translation")),
    (_("XLIFF files"), ("*.xlf", "*.xliff"), ("application/x-xliff", "application/x-xliff+xml")),
    (_("TBX files"), ("*.tbx", ), ("application/x-tbx", )),
    (_("TMX files"), ("*.tmx", ), ("application/x-tmx", )),
    (_("Wordfast TM files"), None, ("text/x-wordfast", )),
    #(_("Qt Linguist files"), ("*.ts", ), ("application/x-linguist", )),
    #(_("Qt .qm files"), ("*.qm", ), ("application/x-qm", )),
    (_("Gettext MO files"), ("*.mo", "*.gmo"), ("application/x-gettext-translation", )),
]

def file_open_chooser(self, destroyCallback=None):
    chooser = gtk.FileChooserDialog(
            _('Choose a translation file'),
            None,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)
    )
    if path.exists(pan_app.settings.general["lastdir"]):
        chooser.set_current_folder(pan_app.settings.general["lastdir"])

    chooser.set_default_response(gtk.RESPONSE_OK)

    all_supported_filter = gtk.FileFilter()
    all_supported_filter.set_name(_("All Supported Files"))
    chooser.add_filter(all_supported_filter)
    for name, wildcards, mimetypes in supported_types:
        new_filter = gtk.FileFilter()
        new_filter.set_name(name)
        if wildcards:
            for wildcard in wildcards:
                new_filter.add_pattern(wildcard)
                all_supported_filter.add_pattern(wildcard)
                for extension in factory.decompressclass.keys():
                    new_filter.add_pattern("%s.%s" % (wildcard, extension))
                    all_supported_filter.add_pattern("%s.%s" % (wildcard, extension))
        if mimetypes:
            for mimetype in mimetypes:
                new_filter.add_mime_type(mimetype)
                all_supported_filter.add_mime_type(mimetype)
        chooser.add_filter(new_filter)
    all_filter = gtk.FileFilter()
    all_filter.set_name(_("All Files"))
    all_filter.add_pattern("*")
    chooser.add_filter(all_filter)

    if destroyCallback:
        chooser.connect("destroy", destroyCallback)

    return chooser
