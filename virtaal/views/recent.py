#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
