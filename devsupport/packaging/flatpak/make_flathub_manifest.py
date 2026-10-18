#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Write a Flathub submission: io.github.translate.Virtaal.yml building
Virtaal from a git commit instead of this checkout, plus the files it
refers to.

  make_flathub_manifest.py --commit SHA [--tag TAG] OUTDIR"""

import argparse
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = 'io.github.translate.Virtaal.yml'
# Files the manifest refers to by relative path.
EXTRA_FILES = ('virtaal-python-deps.yaml', 'intltool-perl5.26-regex-fixes.patch')
URL = 'https://github.com/translate/virtaal.git'
# Virtaal's own source: this checkout, with whatever follows its path
# (comments, a skip list) up to the end of the file.
LOCAL_SOURCE = re.compile(r'^    sources:\n      - type: dir\n        path: \.\./\.\./\.\.\n(?:        .*\n|\s*\n)*\Z', re.M)


def flathub_manifest(text, commit, tag=None):
    """text, with Virtaal's local checkout source replaced by a git one."""
    if not LOCAL_SOURCE.search(text):
        raise ValueError("the manifest's local checkout source wasn't found")
    lines = ['    sources:', '      - type: git', '        url: ' + URL]
    if tag:
        lines.append('        tag: ' + tag)
    lines.append('        commit: ' + commit)
    return LOCAL_SOURCE.sub(lambda _match: '\n'.join(lines) + '\n', text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--commit', required=True)
    parser.add_argument('--tag')
    parser.add_argument('outdir', type=Path)
    args = parser.parse_args(argv)

    args.outdir.mkdir(parents=True, exist_ok=True)
    text = (HERE / MANIFEST).read_text(encoding='utf-8')
    (args.outdir / MANIFEST).write_text(flathub_manifest(text, args.commit, args.tag), encoding='utf-8')
    for name in EXTRA_FILES:
        shutil.copyfile(HERE / name, args.outdir / name)


if __name__ == '__main__':
    main()
