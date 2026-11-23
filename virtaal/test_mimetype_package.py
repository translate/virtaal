#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Content types GIO assigns with Virtaal's shared-mime-info package installed."""

import json
import os
import re
import shutil
import subprocess
import sys
from codecs import BOM_UTF16_BE, BOM_UTF16_LE

import pytest

PACKAGE_IN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "share", "mime", "packages", "virtaal-mimetype.xml.in")

FREEDESKTOP_XML = "/usr/share/mime/packages/freedesktop.org.xml"

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("update-mime-database")
    or not os.path.exists(FREEDESKTOP_XML),
    reason="needs GIO's xdgmime backend (Linux) and shared-mime-info")

# The header's user list names everyone who has worked on the TM, so
# "%Wordfast TM" can sit a few hundred bytes in.
USER_LISTS = {
    "one user": "%User ID,TT,TT Translate-Toolkit",
    "team": ("%User ID,AB,AB Anna Botha,CD,CD Carel du Plessis,EF,EF Elsa Fourie,"
             "GH,GH Gert Human,MT! Machine translation (15),AL! Alignment (10)"),
}


def _wordfast_tm(user_list):
    return (f"%20261123~020706\t{user_list}\t%TU=00000001\t"
            "%EN-US\t%Wordfast TM v.5.51w9/00\t%AF-ZA\t%---00000001\t\t\t\t\r\n"
            "20261123~020706\tAB\t0\tEN-US\tHello\tAF-ZA\tHallo\t\t\t\t\r\n")


GUESS = """
import json, sys
from gi.repository import Gio
print(json.dumps({name: Gio.content_type_guess(name, open(path, "rb").read())[0]
                  for name, path in json.loads(sys.argv[1]).items()}))
"""


def _guess(tmp_path, samples):
    """Return GIO's guessed content type for each {name: bytes} sample."""
    data_dir = tmp_path / "data"
    packages = data_dir / "mime" / "packages"
    packages.mkdir(parents=True)
    with open(PACKAGE_IN, encoding="utf-8") as f:
        package = re.sub(r'\s+(xmlns:its|its:\w+)="[^"]*"', "", f.read())
    (packages / "virtaal-mimetype.xml").write_text(package, encoding="utf-8")
    shutil.copy(FREEDESKTOP_XML, packages)
    subprocess.run(["update-mime-database", str(data_dir / "mime")], check=True)

    paths = {}
    for name, content in samples.items():
        path = tmp_path / "samples" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(content)
        paths[name] = str(path)
    env = dict(os.environ, XDG_DATA_DIRS=str(data_dir), XDG_DATA_HOME=str(tmp_path / "home"))
    out = subprocess.run([sys.executable, "-c", GUESS, json.dumps(paths)], env=env,
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("user_list", USER_LISTS.values(), ids=USER_LISTS.keys())
def test_wordfast_tm_is_recognised_by_content_in_each_encoding(tmp_path, user_list):
    pytest.importorskip("gi.repository.Gio")
    tm = _wordfast_tm(user_list)
    samples = {
        "ascii": tm.encode("latin-1"),
        "utf16le-bom": BOM_UTF16_LE + tm.encode("utf-16-le"),
        "utf16le": tm.encode("utf-16-le"),
        "utf16be-bom": BOM_UTF16_BE + tm.encode("utf-16-be"),
        "utf16be": tm.encode("utf-16-be"),
        "plain": b"Some notes\tnot a translation memory\n",
    }

    types = _guess(tmp_path, samples)

    assert types == {
        "ascii": "text/x-wordfast",
        "utf16le-bom": "text/x-wordfast",
        "utf16le": "text/x-wordfast",
        "utf16be-bom": "text/x-wordfast",
        "utf16be": "text/x-wordfast",
        "plain": "text/plain",
    }
