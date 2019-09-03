#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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

from gi.repository import Gtk
from translate.storage import factory

rf = Gtk.RecentFilter()
for name, extensions, mimetypes in factory.supported_files():
    if extensions:
        for extension in extensions:
            if extension in ("txt"):
                continue
            rf.add_pattern("*.%s" % extension)
            for compress_extension in factory.decompressclass.keys():
                rf.add_pattern("*.%s.%s" % (extension, compress_extension))
    if mimetypes:
        for mimetype in mimetypes:
            rf.add_mime_type(mimetype)
for app in ("virtaal", "poedit", "kbabel", "lokalize", "gtranslator"):
    rf.add_application(app)

rm = Gtk.RecentManager.get_default()

rc = Gtk.RecentChooserMenu()
# For now we don't handle non-local files yet
rc.set_local_only(True)
rc.set_show_not_found(False)
rc.set_show_numbers(True)
rc.set_show_tips(True)
rc.set_sort_type(Gtk.RecentSortType.MRU)
rc.add_filter(rf)
rc.set_limit(15)
