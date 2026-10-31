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

# Script variants translate-toolkit's list lacks, which simplify_to_common()
# would turn into the base language and its script (#4681): code -> (name,
# base language for the plural forms).
VARIANT_LANGUAGES = {
    'be@latin': ('Belarusian (Latin)', 'be'),
    'sr@latin': ('Serbian (Latin)', 'sr'),
    'uz@cyrillic': ('Uzbek (Cyrillic)', 'uz'),
}
# A script subtag (sr_Latn, sr_Latn_RS) names the same variant.
SCRIPT_VARIANTS = {'Latn': 'latin', 'Cyrl': 'cyrillic'}


def same_language(code, langcode):
    """Whether a file's own language C{code} (e.g. "en-US") is the language
        Virtaal knows as C{langcode} (e.g. "en")."""
    return bool(code) and LanguageModel(code).code == langcode


class LanguageModel(BaseModel):
    """
    A simple container for language information for use by the C{LanguageController}
    and C{LanguageView}.
    """

    __gtype_name__ = 'LanguageModel'

    languages = {}

    # INITIALIZERS #
    def __init__(self, langcode='und'):
        """Constructor.
            Looks up the language information based on the given language code
            (C{langcode})."""
        super().__init__()
        if not self.languages:
            self.languages.update(toolkit_langs)
            for code, (name, base) in VARIANT_LANGUAGES.items():
                if base in toolkit_langs:
                    self.languages.setdefault(code, (name,) + tuple(toolkit_langs[base][1:]))
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
        langcode = self._script_variant(langcode)
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

        self.name = gettext_lang(self.languages[langcode][0], langcode)
        self.code = langcode
        self.nplurals = self.languages[langcode][1]
        self.plural = self.languages[langcode][2]

    def _script_variant(self, langcode):
        """sr_Latn or sr_Latn_RS as sr@latin, when that is a known language."""
        parts = langcode.replace('-', '_').split('_')
        if len(parts) > 1 and parts[1] in SCRIPT_VARIANTS:
            variant = '%s@%s' % (parts[0], SCRIPT_VARIANTS[parts[1]])
            if variant in self.languages:
                return variant
        return langcode

    def _match_normalized_langcode(self, langcode):
        languages_keys = list(self.languages.keys())
        normalized_keys = [data.normalize_code(lang) for lang in languages_keys]
        i =  normalized_keys.index(data.normalize_code(langcode))
        return languages_keys[i]
