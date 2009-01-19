#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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

from translate.lang.data import languages, tr_lang

from virtaal.common import pan_app

from basemodel import BaseModel


class LanguageModel(BaseModel):
    """
    A simple container for language information for use by the C{LanguageController}
    and C{LanguageView}.
    """

    __gtype_name__ = 'LanguageModel'

    # INITIALIZERS #
    def __init__(self, langcode='und', more_langs={}):
        """Constructor.
            Looks up the language information based on the given language code
            (C{langcode})."""
        super(LanguageModel, self).__init__()
        self.gettext_lang = tr_lang(pan_app.settings.language["uilang"])
        languages.update(more_langs)
        self.load(langcode)


    # SPECIAL METHODS #
    def __eq__(self, otherlang):
        """Check that the C{code}, C{nplurals} and C{plural} attributes are the
            same. The C{name} attribute may differ, seeing as it is localised.

            @type  otherlang: LanguageModel
            @param otherlang: The language to compare the current instance to."""
        return  isinstance(otherlang, LanguageModel) and \
                self.code     == otherlang.code and \
                self.nplurals == otherlang.nplurals and \
                self.plural   == otherlang.plural


    # METHODS #
    def load(self, langcode):
        #TODO: langcode = getstandardcode(langcode)
        # FIXME: HACKS below
        if langcode == 'en-US':
            langcode = 'en'

        if langcode not in languages:
            raise Exception('Language not found: %s' % (langcode))

        self.name = self.gettext_lang(languages[langcode][0])
        self.code = langcode
        self.nplurals = languages[langcode][1]
        self.plural = languages[langcode][2]
