#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Generates the [CustomMessages] block virtaal.iss #includes for its own
file-type strings (see build_installer.ps1). Run with the same Python
environment bin/virtaal runs with.

Only the strings that are also its:translate="yes" in
share/mime/packages/virtaal-mimetype.xml.in are covered here - those are
already extracted into po/virtaal.pot and translated across po/*.po, so
this needs no new translator work, just reusing what's already there.
Virtaal's other installer-only strings (the fileassoc task description,
"PO Translation File", "SDL XLIFF Translation File", "Gettext Message
File", "Fluent Translation File", "Edit with Virtaal") have no existing
translation to reuse and stay hardcoded English literals.

Usage: generate_installer_translations.py OUTPUT_PATH
"""

import sys
from pathlib import Path

from translate.storage import pypo

REPO_ROOT = Path(__file__).resolve().parents[3]

# Inno [Languages] Name: -> po/LINGUAS code. Hand-maintained same as
# virtaal.iss's own [Languages] section (see issue #3740 - both would
# ideally come from one generated source instead of two hand-maintained
# ones).
INNO_NAME_TO_PO_CODE = {
    "arabic": "ar",
    "brazilianportuguese": "pt_BR",
    "bulgarian": "bg",
    "catalan": "ca",
    "chinesetraditional": "zh_TW",
    "czech": "cs",
    "danish": "da",
    "dutch": "nl",
    "finnish": "fi",
    "french": "fr",
    "german": "de",
    "hebrew": "he",
    "italian": "it",
    "japanese": "ja",
    "lithuanian": "lt",
    "polish": "pl",
    "portuguese": "pt",
    "russian": "ru",
    "spanish": "es",
    "swedish": "sv",
    "thai": "th",
    "turkish": "tr",
    "ukrainian": "uk",
    "afrikaans": "af",
    "greek": "el",
    "englishbritish": "en_GB",
    "basque": "eu",
    "galician": "gl",
    "vietnamese": "vi",
    "belarusian": "be",
    "bengali": "bn_IN",
    "valencian": "ca@valencia",
    "icelandic": "is",
    "asturian": "ast",
}

# CustomMessages key -> msgid, for the strings shared with
# share/mime/packages/virtaal-mimetype.xml.in.
MESSAGE_KEY_TO_MSGID = {
    "TmxFileType": "TMX Translation Memory",
    "TbxFileType": "TBX Glossary",
    "QmFileType": "Qt Message File",
    "QphFileType": "Qt Phrase Book",
    "XliffFileType": "XLIFF Translation File",
}


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


def build_custom_messages():
    lines = ["[CustomMessages]"]
    for key, msgid in MESSAGE_KEY_TO_MSGID.items():
        lines.append(f"{key}={msgid}")
    for inno_name, po_code in INNO_NAME_TO_PO_CODE.items():
        messages = translated_messages(po_code)
        for key, msgid in MESSAGE_KEY_TO_MSGID.items():
            if msgid in messages:
                lines.append(f"{inno_name}.{key}={messages[msgid]}")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        print("usage: generate_installer_translations.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(1)
    # utf-8-sig: Inno Setup only treats an included script file as UTF-8
    # if it starts with a BOM, otherwise it assumes the local codepage
    # and corrupts every non-Latin-script translation here.
    Path(sys.argv[1]).write_text(build_custom_messages(), encoding="utf-8-sig")


if __name__ == "__main__":
    main()
