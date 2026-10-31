#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The parts of the macOS and Windows PyInstaller specs they share."""

from pathlib import Path

import babel_data
import translate

from virtaal.support.libi18n.lite import (
    bundle_languages,
    expected_catalogs,
    is_unused_catalog,
    mismatched_catalogs,
    missing_catalogs,
    read_linguas,
)

COPYRIGHT = "Copyright 2007-2026 Translate. GNU General Public License."

# translate-toolkit's own data (langmodels/, the ngram language models
# translate.lang.identify.LanguageIdentifier detects languages with, and
# stoplist-en), which translate.misc.file_discovery looks for under
# share/ when frozen. Without it the language-pair selector
# (get_detected_langs(), langcontroller.py) crashes with
# ValueError: Could not find "langmodels".
TRANSLATE_SHARE = Path(translate.__file__).parent / "share"

# lxml modules nothing imports; PyInstaller's lxml hook collects them all.
UNUSED_LXML = [
    "lxml.objectify", "lxml.sax", "lxml.builder", "lxml.html.builder", "lxml.html.diff",
    "lxml.html._difflib", "lxml.html._diffcommand", "lxml.isoschematron",
]

# devsupport isn't needed at runtime in a frozen build: its one consumer
# (profiling support) is `if not packaged:`-gated off in virtaal/cli.py.
EXCLUDES = ["FixTk", "tcl", "tk", "_tkinter", "tkinter", "Tkinter", "devsupport"] + UNUSED_LXML

EXE_OPTIONS = {
    "exclude_binaries": True,
    "name": "virtaal",
    "debug": False,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": False,
    "console": False,
}

COLLECT_OPTIONS = {"strip": False, "upx": False, "name": "virtaal"}


def languages(root):
    """The UI languages this build ships; the gi hooks bundle GTK's and
        GLib's own catalogs for these (and the languages gettext falls back
        to for them) only, not for every language the libraries translate."""
    return read_linguas(Path(root) / "po" / "LINGUAS")


def mo_files(root):
    """PyInstaller datas for Virtaal's compiled catalogs under root/mo."""
    mo_dir = Path(root) / "mo"
    return [
        (str(p), str(Path("share", "locale") / p.relative_to(mo_dir).parent / "LC_MESSAGES"))
        for p in mo_dir.rglob("*.mo")
    ]


def datas(root):
    """PyInstaller datas every build ships, catalogs aside."""
    root = Path(root)
    return [
        (str(root / "share" / "virtaal"), "share/virtaal"),
        (str(root / "share" / "icons"), "share/icons"),
        (str(TRANSLATE_SHARE), "share"),
        # virtaal/support/authors.py reads this at the bundle root - it
        # stays a real top-level file (not under share/) so it's still
        # recognised by GitHub/the AUTHORS convention in a checkout too.
        (str(root / "AUTHORS.md"), "."),
    ]


def not_test(name):
    leaf = name.rpartition(".")[2]
    return not (leaf.startswith("test_") or leaf == "conftest")


def not_enchant_dialog(name):
    return name not in (
        "enchant.checker.CmdLineChecker",
        "enchant.checker.GtkSpellCheckerDialog",
        "enchant.checker.wxSpellCheckerDialog",
    )


def hiddenimports(enchant=True):
    """Modules imported by name at runtime, which PyInstaller can't see:
        virtaal's plugins (plugincontroller.py __import__()s them by
        name), virtaal/support/tmserver.py (reached only through bin/
        virtaal's --run-module, see localtm.py), the translate.storage
        backends factory.getobject() picks, and enchant's submodules."""
    from PyInstaller.utils.hooks import collect_submodules

    return (
        collect_submodules("virtaal", filter=not_test)
        + collect_submodules("translate.storage")
        + (collect_submodules("enchant", filter=not_enchant_dialog) if enchant else [])
    )


def hooksconfig(langs, module_versions=None, **gi):
    """PyInstaller hooksconfig: GTK 3 and the shipped languages, plus
        any other gi hook options."""
    return {
        "gi": {
            "module-versions": {"Gtk": "3.0", **(module_versions or {})},
            "languages": bundle_languages(langs),
            **gi,
        },
    }


def trim(toc, root):
    """Analysis datas without the Babel locale data, catalogs and
        pycountry databases a frozen build never reads."""
    toc = babel_data.trim(toc, str(Path(root) / "po"))
    return [entry for entry in toc if not is_unused_catalog(entry[0])]


def check_catalogs(toc, catalogs, langs):
    """Exits unless the bundle has Virtaal's catalogs (mo_files()) where
        it ships them, and every shipped language has its virtaal.mo, and
        GTK's and GLib's catalogs wherever this host's libraries or a lite
        catalog provide one."""
    # PyInstaller keeps the first datas entry for a destination: our merged
    # lite catalogs, listed in the spec's datas, must beat the copies the
    # library hooks collect at the same path.
    mismatched = mismatched_catalogs(toc, catalogs)
    if mismatched:
        raise SystemExit("Bundled another copy instead of Virtaal's catalog: %r" % mismatched)
    missing = missing_catalogs(toc, expected_catalogs(langs, catalogs))
    if missing:
        raise SystemExit("Shipped languages missing catalogs: %r" % missing)
