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
# Virtaal's install command with the comments above it; the commit file
# goes in just before them.
PIP_INSTALL = re.compile(r'^(?:      #.*\n)*      - pip3 install ', re.M)


def flathub_manifest(text, commit, tag=None):
    """text, with Virtaal's local checkout source replaced by a git one
    and the commit written for the About dialog."""
    # It goes into a shell command in the manifest.
    if not re.fullmatch(r'[0-9a-f]{7,40}', commit):
        raise ValueError("not a commit hash: %r" % commit)
    if not LOCAL_SOURCE.search(text):
        raise ValueError("the manifest's local checkout source wasn't found")
    lines = ['    sources:', '      - type: git', '        url: ' + URL]
    if tag:
        lines.append('        tag: ' + tag)
    lines.append('        commit: ' + commit)
    text = LOCAL_SOURCE.sub(lambda _match: '\n'.join(lines) + '\n', text)
    if len(PIP_INSTALL.findall(text)) != 1:
        raise ValueError("the manifest's pip3 install command wasn't found")
    # The About dialog's commit (#4991): a git source has no .git to read it from.
    return PIP_INSTALL.sub(
        lambda match: '      - echo \'commit = "%s"\' > virtaal/_build_info.py\n%s' % (
            commit, match.group(0)),
        text)


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
