#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fetches hunspell dictionaries, pinned, from LibreOffice's dictionaries
repository:
    fetch_dictionaries.py DIR en_US en_GB
Files already in DIR with the right digest aren't fetched again."""

import hashlib
import os
import sys
import time
import urllib.request

COMMIT = "c0865a85eb67dc377f2cf8e8fe2c4fa9e53f0dcb"
RAW = "https://raw.githubusercontent.com/LibreOffice/dictionaries/%s/" % COMMIT

DICTIONARIES = {
    "en_US": {
        "en/en_US.aff": "e746c882dd6f303c2c46e7452804b9201115a6942cfeb15f18f8edf774d2e24e",
        "en/en_US.dic": "f0b1a234bd178bdd01875b2a392a9647f888b8fe879f79c52aae62c2759b3647",
        "en/README_en_US.txt": "168b4c01cb841f766a72f310b065c04d09cff46376c37a81d799593ce751c371",
    },
    "en_GB": {
        "en/en_GB.aff": "0fd6ed120ef28957847d98ba5149b117e27116cf81b5aa36208453f6755a36fd",
        "en/en_GB.dic": "04e90f34f5263bf26780e9c4a442e9ad16584e227af49ddd1b3b21b01df5b29c",
        "en/README_en_GB.txt": "18b5833de60a52ffcb6e5b6b5048bb5a5d910acfecd5b096985b77058223880c",
    },
}


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def fetch(directory, names, get=_get):
    """Puts each dictionary's files in directory; returns their paths."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for name in names:
        for source, digest in DICTIONARIES[name].items():
            path = os.path.join(directory, os.path.basename(source))
            if not (os.path.isfile(path) and _sha256(path) == digest):
                data = get(RAW + source)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise SystemExit("%s: unexpected sha256" % source)
                with open(path, "wb") as f:
                    f.write(data)
            paths.append(path)
    return paths


if __name__ == "__main__":
    for line in fetch(sys.argv[1], sys.argv[2:]):
        print(line)
