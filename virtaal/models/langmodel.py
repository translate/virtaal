#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging

from translate.lang import data
from translate.lang.data import languages as toolkit_langs

from virtaal.common.pan_app import ui_language
from virtaal.support.translate_compat import tr_lang

from .basemodel import BaseModel

gettext_lang = tr_lang(ui_language)

class LanguageModel(BaseModel):
    """
    A simple container for language information for use by the C{LanguageController}
    and C{LanguageView}.
    """

    __gtype_name__ = 'LanguageModel'

    languages = {}

    # INITIALIZERS #
    def __init__(self, langcode='und', more_langs={}):
        """Constructor.
            Looks up the language information based on the given language code
            (C{langcode})."""
        super().__init__()
        if not self.languages:
            self.languages.update(toolkit_langs)
        self.languages.update(more_langs)
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
        #FIXME: what if we get language code with different capitalization?
        if langcode not in self.languages:
            try:
                langcode = self._match_normalized_langcode(langcode)
            except ValueError:
                langcode = data.simplify_to_common(langcode)
                if langcode not in self.languages:
                    try:
                        langcode = self._match_normalized_langcode(langcode)
                    except ValueError:
                        logging.info("unknown language %s" % langcode)
                        self.name = langcode
                        self.code = langcode
                        self.nplurals = 0
                        self.plural = ""
                        return

        self.name = gettext_lang(self.languages[langcode][0])
        self.code = langcode
        self.nplurals = self.languages[langcode][1]
        self.plural = self.languages[langcode][2]

    def _match_normalized_langcode(self, langcode):
        languages_keys = list(self.languages.keys())
        normalized_keys = [data.normalize_code(lang) for lang in languages_keys]
        i =  normalized_keys.index(data.normalize_code(langcode))
        return languages_keys[i]
