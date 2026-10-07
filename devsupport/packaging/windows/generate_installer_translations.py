#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Generates the [Languages] and [CustomMessages] sections virtaal.iss
#includes (see build_installer.ps1). Run with the same Python
environment bin/virtaal runs with.

The installer offers po/LINGUAS ∩ INNO_LANGUAGES. A po/LINGUAS code
missing from both INNO_LANGUAGES and NO_INNO_LANGUAGE is an error, so a
newly shipped translation forces a decision about its installer
language.

[CustomMessages] holds virtaal.iss's own strings, translated from
po/*.po. Each msgid must be in po/virtaal.pot - the installer-only
ones are listed in devsupport/tmp_strings.py.

Usage: generate_installer_translations.py OUTPUT_PATH
"""

import sys
from pathlib import Path

from translate.storage import pypo

REPO_ROOT = Path(__file__).resolve().parents[3]
LANGUAGES_DIR = Path(__file__).resolve().parent / "languages"

# po/LINGUAS code -> vendored Inno Setup messages file in languages\,
# all copied unmodified from jrsoftware/issrc's Files/Languages
# (Unofficial/ for the ones Inno doesn't ship itself). The [Languages]
# Name is the file's lowercased stem.
INNO_LANGUAGES = {
    "af": "Afrikaans.isl",
    "ar": "Arabic.isl",
    # Last updated for Inno 4.0.x - more wizard strings fall back to
    # English than for any other language here.
    "ast": "Asturian.isl",
    "be": "Belarusian.isl",
    "bg": "Bulgarian.isl",
    # Generic Bengali, not bn_IN specifically.
    "bn_IN": "Bengali.islu",
    "ca": "Catalan.isl",
    "ca@valencia": "Valencian.isl",
    "cs": "Czech.isl",
    "da": "Danish.isl",
    "de": "German.isl",
    "el": "Greek.isl",
    "en_GB": "EnglishBritish.isl",
    "es": "Spanish.isl",
    "eu": "Basque.isl",
    "fi": "Finnish.isl",
    "fr": "French.isl",
    "gl": "Galician.isl",
    "he": "Hebrew.isl",
    "hu": "Hungarian.isl",
    "is": "Icelandic.isl",
    "it": "Italian.isl",
    "ja": "Japanese.isl",
    "ko": "Korean.isl",
    "lt": "Lithuanian.isl",
    "ne": "Nepali.islu",
    "nl": "Dutch.isl",
    "pl": "Polish.isl",
    "pt": "Portuguese.isl",
    "pt_BR": "BrazilianPortuguese.isl",
    "ru": "Russian.isl",
    "si": "Sinhala.islu",
    "sk": "Slovak.isl",
    "sr": "SerbianCyrillic.isl",
    "sv": "Swedish.isl",
    "th": "Thai.isl",
    "tr": "Turkish.isl",
    "uk": "Ukrainian.isl",
    "vi": "Vietnamese.isl",
    "zh_CN": "ChineseSimplified.isl",
    "zh_TW": "ChineseTraditional.isl",
}

# po/LINGUAS codes whose installer stays in English.
NO_INNO_LANGUAGE = {
    "ak", "am", "cgg", "en_ZA", "ff", "fo", "lg", "nso", "pa", "son",  # codespell:ignore fo
    "st", "sw", "te", "zu",  # codespell:ignore te
    # Inno's Occitan.isl is Aranese, not the Occitan oc.po is in.
    "oc",
}

# CustomMessages key -> msgid.
MESSAGE_KEY_TO_MSGID = {
    "FileAssocTask": "Associate Virtaal with translation file types (.po, .xlf, .tmx, ...)",
    "EditWithVirtaal": "Edit with Virtaal",
    "PoFileType": "Gettext PO file",
    "MoFileType": "Gettext MO file",
    "XliffFileType": "XLIFF Translation File",
    "SdlXliffFileType": "SDL XLIFF Translation File",
    "QmFileType": "Qt Message File",
    "TbxFileType": "TBX Glossary",
    "TmxFileType": "TMX Translation Memory",
    "QphFileType": "Qt Phrase Book",
    "FluentFileType": "Fluent file",
}


def inno_name(po_code):
    return Path(INNO_LANGUAGES[po_code]).stem.lower()


def read_linguas():
    text = (REPO_ROOT / "po" / "LINGUAS").read_text(encoding="utf-8")
    return [code for line in text.splitlines() if (code := line.split("#")[0].strip())]


def installer_languages(linguas):
    unmapped = [code for code in linguas if code not in INNO_LANGUAGES and code not in NO_INNO_LANGUAGE]
    if unmapped:
        raise ValueError(
            "po/LINGUAS codes with no installer language decision: %s - add each to "
            "INNO_LANGUAGES (vendoring its .isl) or NO_INNO_LANGUAGE" % ", ".join(unmapped)
        )
    return sorted((code for code in linguas if code in INNO_LANGUAGES), key=inno_name)


def translated_messages(po_code):
    po_path = REPO_ROOT / "po" / f"{po_code}.po"
    if not po_path.exists():
        return {}
    store = pypo.pofile(po_path.read_bytes())
    wanted = set(MESSAGE_KEY_TO_MSGID.values())
    found = {}
    for unit in store.units:
        if unit.source in wanted and unit.istranslated() and not unit.isfuzzy():
            found[unit.source] = str(unit.target)
    return found


def build_languages(po_codes):
    lines = ["[Languages]", 'Name: "english"; MessagesFile: "compiler:Default.isl"']
    for code in po_codes:
        lines.append(f'Name: "{inno_name(code)}"; MessagesFile: "languages\\{INNO_LANGUAGES[code]}"')
    return lines


def build_custom_messages(po_codes):
    lines = ["[CustomMessages]"]
    for key, msgid in MESSAGE_KEY_TO_MSGID.items():
        lines.append(f"{key}={msgid}")
    for code in po_codes:
        messages = translated_messages(code)
        for key, msgid in MESSAGE_KEY_TO_MSGID.items():
            if msgid in messages:
                lines.append(f"{inno_name(code)}.{key}={messages[msgid]}")
    return lines


def build_include(linguas):
    po_codes = installer_languages(linguas)
    return "\n".join(build_languages(po_codes) + [""] + build_custom_messages(po_codes)) + "\n"


def main():
    if len(sys.argv) != 2:
        print("usage: generate_installer_translations.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(1)
    try:
        include = build_include(read_linguas())
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    # utf-8-sig: Inno Setup only treats an included script file as UTF-8
    # if it starts with a BOM, otherwise it assumes the local codepage
    # and corrupts every non-Latin-script translation here.
    Path(sys.argv[1]).write_text(include, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
