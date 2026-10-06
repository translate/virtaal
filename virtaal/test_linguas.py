#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import glob
import os

PO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "po")


def _read(name):
    with open(os.path.join(PO_DIR, name), encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip() and not line.startswith("#")]


def _excluded():
    return {line.split("#")[0].strip(): line.partition("#")[2].strip() for line in _read("LINGUAS-excluded")}


def test_every_catalog_is_shipped_or_excluded():
    # setup.py only builds what po/LINGUAS lists, so a .po missing from
    # both files never ships.
    catalogs = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(PO_DIR, "*.po"))}

    assert sorted(catalogs - set(_read("LINGUAS")) - set(_excluded())) == []


def test_exclusions_are_not_shipped():
    assert sorted(set(_read("LINGUAS")) & set(_excluded())) == []


def test_every_exclusion_has_a_catalog_and_a_reason():
    for lang, reason in _excluded().items():
        assert os.path.isfile(os.path.join(PO_DIR, lang + ".po")), lang
        assert reason, lang
