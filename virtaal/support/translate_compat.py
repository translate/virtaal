# -*- coding: utf-8 -*-
#
# Copyright 2007-2011 Zuza Software Foundation
#
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
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
# along with this program; if not, see <http://www.gnu.org/licenses/>.

# --- Vendored into Virtaal ---
# The functions/data below are copied verbatim from translate-toolkit
# (PyPI: translate-toolkit), file translate/lang/data.py, at:
#   repo:      https://github.com/translate/translate
#   tag:       2.5.1
#   commit:    1dc4f89bdb35edc71177eb23533764b06532db11
#   blob sha:  fe7cd208c2de7278280f3d5c0fcbd724cfb44721
# tr_lang() and forceunicode() were removed from translate-toolkit with no
# replacement between releases 3.2.0 and 3.3.0 (early 2021). Only the
# handful of module-level names needed by tr_lang()/forceunicode() are
# extracted here (this file itself, as a curated excerpt, is therefore
# necessarily new - but every function/constant body below is untouched
# from the commit cited above). See the follow-up commit for the
# Python-3-only adaptation (dropping the six dependency).

"""Small helpers that used to live in translate.lang.data (see the
vendoring note above for exactly where these came from and why).
"""

import gettext
import locale
import os
import re

try:
    import pycountry
except ImportError:
    pycountry = None


_fixed_names = {
    "Asturian; Bable; Leonese; Asturleonese": "Asturian",
    "Bokmål, Norwegian; Norwegian Bokmål": "Norwegian Bokmål",
    "Catalan; Valencian": "Catalan",
    "Central Khmer": "Khmer",
    "Chichewa; Chewa; Nyanja": "Chewa; Nyanja",
    "Divehi; Dhivehi; Maldivian": "Divehi",
    "Dutch; Flemish": "Dutch",
    "Filipino; Pilipino": "Filipino",
    "Gaelic; Scottish Gaelic": "Scottish Gaelic",
    "Greek, Modern (1453-)": "Greek",
    "Interlingua (International Auxiliary Language Association)": "Interlingua",
    "Kirghiz; Kyrgyz": "Kirghiz",
    "Klingon; tlhIngan-Hol": "Klingon",
    "Limburgan; Limburger; Limburgish": "Limburgish",
    "Low German; Low Saxon; German, Low; Saxon, Low": "Low German",
    "Luxembourgish; Letzeburgesch": "Luxembourgish",
    "Ndebele, South; South Ndebele": "Southern Ndebele",
    "Norwegian Nynorsk; Nynorsk, Norwegian": "Norwegian Nynorsk",
    "Occitan (post 1500)": "Occitan",
    "Panjabi; Punjabi": "Punjabi",
    "Pedi; Sepedi; Northern Sotho": "Northern Sotho",
    "Pushto; Pashto": "Pashto",
    "Sinhala; Sinhalese": "Sinhala",
    "Songhai languages": "Songhay",
    "Sotho, Southern": "Sotho",
    "Spanish; Castilian": "Spanish",
    "Uighur; Uyghur": "Uyghur",
}


dialect_name_re = re.compile(r"(.+)\s\(([^)\d]{,25})\)$")
# The limit of 25 characters on the country name is so that "Interlingua (...)"
# (see above) is correctly interpreted.


def tr_lang(langcode=None):
    """Gives a function that can translate a language name, even in the form
    ``"language (country)"``, into the language with iso code langcode, or the
    system language if no language is specified.
    """
    langfunc = gettext_lang(langcode)
    countryfunc = gettext_country(langcode)

    def handlelanguage(name):
        match = dialect_name_re.match(name)
        if match:
            language, country = match.groups()
            if country != "macrolanguage":
                return (
                    u"%s (%s)"
                    % (_fix_language_name(langfunc(language)),
                       countryfunc(country)))
        return _fix_language_name(langfunc(name))

    return handlelanguage


def _fix_language_name(name):
    """Identify and replace some unsightly names present in iso-codes.

    If the name is present in _fixed_names we assume it is untranslated and we
    replace it with a more usable rendering.  If the remaining part is long and
    includes a semi-colon, we only take the text up to the semi-colon to keep
    things neat.
    """
    if name in _fixed_names:
        return _fixed_names[name]
    elif len(name) > 11:
        # These constants are somewhat arbitrary, but testing with the Japanese
        # translation of ISO codes suggests these as the upper bounds.
        split_point = name[5:].find(';')
        if split_point >= 0:
            return name[:5+split_point]
    return name


def gettext_domain(langcode, domain, localedir=None):
    """Returns a gettext function for given iso domain"""
    kwargs = dict(
        domain=domain,
        localedir=localedir,
        fallback=True)
    if langcode:
        kwargs['languages'] = [langcode]
    elif os.name == "nt":
        # On Windows the default locale is not used for some reason
        kwargs['languages'] = [locale.getdefaultlocale()[0]]
    t = gettext.translation(**kwargs)
    return t.gettext


def gettext_lang(langcode=None):
    """Returns a gettext function to translate language names into the given
    language, or the system language if no language is specified.
    """
    if pycountry is None:
        return gettext_domain(langcode, 'iso_639')
    return gettext_domain(langcode, 'iso639-3', pycountry.LOCALES_DIR)


def gettext_country(langcode=None):
    """Returns a gettext function to translate country names into the given
    language, or the system language if no language is specified.
    """
    if pycountry is None:
        return gettext_domain(langcode, 'iso_3166')
    return gettext_domain(langcode, 'iso3166', pycountry.LOCALES_DIR)


def forceunicode(string):
    """Ensures that the string is in unicode.

    :param string: A text string
    :type string: Unicode, String
    :return: String converted to Unicode and normalized as needed.
    :rtype: Unicode
    """
    if string is None:
        return None
    from translate.storage.placeables import StringElem
    if isinstance(string, bytes):
        encoding = getattr(string, "encoding", "utf-8")
        string = string.decode(encoding)
    elif isinstance(string, StringElem):
        string = str(string)
    return string
