#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk, GdkPixbuf

from virtaal import __version__
from virtaal.common import pan_app
from virtaal.support import openmailto
from virtaal.support.authors import find_authors_md, parse_contributors


class AboutDialog(Gtk.AboutDialog):
    def __init__(self, parent):
        super().__init__()
        self._register_uri_handlers()
        self.set_name("Virtaal")
        self.set_version(__version__.version_string())
        self.set_copyright(_("Copyright © 2007-2026 Zuza Software Foundation"))
        # l10n: Please retain the literal name "Virtaal", but feel free to
        # additionally transliterate the name and to add a translation of "For Language", which is what the name means.
        self.set_comments(_("Virtaal is a program for doing translation.") + "\n\n" +
            _("The initial focus is on software translation (localization or l10n), but we definitely intend it to be useful as a general purpose tool for Computer Aided Translation (CAT)."))
        self.set_license("""This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Library General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <http://www.gnu.org/licenses/>.""")
        self.set_website("https://virtaal.translatehouse.org")
        self.set_website_label(_("Virtaal website"))
        # Contributors: read from AUTHORS.md rather than keeping a
        # second, separately maintained copy here - the two had
        # already drifted (this list used to be a handful of names;
        # AUTHORS.md has the real, fuller one). Personal names aren't
        # run through _() - proper names aren't translated.
        authors_md = find_authors_md()
        authors = parse_contributors(authors_md) if authors_md else []
        if not authors:
            # AUTHORS.md missing or unparsable (shouldn't happen in a
            # normal checkout or a correctly packaged build) - fall
            # back to the founding four rather than an empty tab.
            authors = ["Friedel Wolff", "Dwayne Bailey", "Walter Leibbrandt", "Wynand Winterbach"]

        if pan_app.ui_language == "ar":
            authors = ["علاء عبد الفتاح" if name == "Alaa Abd el Fattah" else name
                       for name in authors]

        # Donors: kept as real literals, not sourced from AUTHORS.md -
        # these are stable, already-translated strings (several
        # locales have real translations, e.g. po/af.po's
        # "Internasionale ontwikkelingsnavorsingsentrum" for the IDRC)
        # and round-tripping them through a data file's exact wording
        # would silently break that lookup on the slightest edit there.
        authors.extend([
            "",  # just for spacing
            _("We thank our donors:"),
            _("The International Development Research Centre"),
            "\thttp://idrc.ca/",
            _("Mozilla Corporation"),
            "\thttp://mozilla.com/",
        ])
        self.set_authors(authors)
        # l10n: Rather than translating, fill in the names of the translators
        self.set_translator_credits(_("translator-credits"))
        self.set_icon(parent.get_icon())
        self.set_logo(GdkPixbuf.Pixbuf.new_from_file(pan_app.get_abs_data_filename(["virtaal", "virtaal_logo.png"])))
        self.set_artists([
                "Heather Bailey",
                ])
        # FIXME entries that we may want to add
        #self.set_documenters()
        self.connect ("response", lambda d, r: d.destroy())
        self.show()

    def on_url(self, dialog, uri, data):
        if data == "mail":
            openmailto.mailto(uri)
        elif data == "url":
            openmailto.open(uri)

    def _register_uri_handlers(self):
        """Register the URL and email handlers

        Use open and mailto from virtaal.support.openmailto
        """
