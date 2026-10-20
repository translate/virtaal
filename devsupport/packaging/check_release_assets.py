#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Check a GitHub release carries every asset it should, then download
each one, compare its sha256 with the digest GitHub recorded, and check
it is the kind of file its name says. Each file is deleted once checked,
and the download folder at the end.

    devsupport/packaging/check_release_assets.py v1.0.0-rc2 [--no-download]

Needs the gh command, logged in. Exits 1 if anything is wrong.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

REPO = 'translate/virtaal'
PRERELEASE_MARKERS = ('-alpha', '-beta', '-rc')


def expected_assets(tag):
    """The files ci.yml's release job attaches for tag."""
    version = tag[1:] if tag.startswith('v') else tag
    names = [
        'virtaal-%s-setup.exe' % version,
        'Virtaal-macos-arm64.dmg',
        'Virtaal-macos-x86_64.dmg',
        'Virtaal-linux-x86_64.flatpak',
        'Virtaal-linux-aarch64.flatpak',
        'Virtaal-linux-x86_64.AppImage',
        'Virtaal-linux-aarch64.AppImage',
    ]
    if '-rc' in tag:
        names.append('virtaal-translation-packs-%s.zip' % tag)
    return names


def is_prerelease_tag(tag):
    return any(marker in tag for marker in PRERELEASE_MARKERS)


def release_problems(tag, release):
    """Problems with the release itself and its asset list."""
    problems = []
    if release.get('prerelease') != is_prerelease_tag(tag):
        problems.append('marked %s, but the tag says %s' % (
            'pre-release' if release.get('prerelease') else 'release',
            'pre-release' if is_prerelease_tag(tag) else 'release'))
    if release.get('draft'):
        problems.append('still a draft')
    assets = {asset['name']: asset for asset in release.get('assets', [])}
    for name in expected_assets(tag):
        asset = assets.get(name)
        if asset is None:
            problems.append('%s: missing' % name)
        elif not asset.get('size'):
            problems.append('%s: empty' % name)
        elif not (asset.get('digest') or '').startswith('sha256:'):
            problems.append('%s: GitHub recorded no sha256 digest' % name)
    for name in sorted(set(assets) - set(expected_assets(tag))):
        problems.append('%s: not expected for %s' % (name, tag))
    return problems


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def kind_problem(name, path):
    """Why the file at path isn't what its name says, or None."""
    with open(path, 'rb') as f:
        head = f.read(64)
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 512))
        tail = f.read(4)
    arch = next((a for a in ('x86_64', 'aarch64', 'arm64') if a in name), None)
    if name.endswith('.exe'):
        ok = head.startswith(b'MZ')
    elif name.endswith('.dmg'):
        ok = tail == b'koly'  # UDIF trailer
    elif name.endswith('.flatpak'):
        # The magic, then the ref: app/<id>/<arch>/<branch>.
        ok = head.startswith(b'flatpak\0') and ('/%s/' % arch).encode() in head
    elif name.endswith('.AppImage'):
        machine = {'x86_64': b'\x3e\x00', 'aarch64': b'\xb7\x00'}[arch]
        ok = head.startswith(b'\x7fELF') and head[8:11] == b'AI\x02' and head[18:20] == machine
    elif name.endswith('.zip'):
        ok = head.startswith(b'PK\x03\x04')
    else:
        return None
    return None if ok else "isn't a .%s file%s" % (name.rsplit('.', 1)[1], ' for ' + arch if arch else '')


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def fetch_release(tag, repo):
    return json.loads(gh('api', 'repos/%s/releases/tags/%s' % (repo, tag)))


def download(tag, repo, name, folder):
    gh('release', 'download', tag, '--repo', repo, '--pattern', name, '--dir', folder)
    return os.path.join(folder, name)


def check_files(tag, repo, release, downloader=download):
    """Download, check and delete each expected asset in turn."""
    problems = []
    assets = {asset['name']: asset for asset in release.get('assets', [])}
    with tempfile.TemporaryDirectory(prefix='virtaal-release-check-') as folder:
        for name in expected_assets(tag):
            asset = assets.get(name)
            if asset is None or not asset.get('size'):
                continue
            try:
                path = downloader(tag, repo, name, folder)
            except (subprocess.CalledProcessError, OSError) as e:
                problems.append('%s: download failed: %s' % (name, getattr(e, 'stderr', '') or e))
                continue
            try:
                found = []
                expected = (asset.get('digest') or '').partition(':')[2]
                actual = sha256(path)
                if expected and actual != expected:
                    found.append('%s: sha256 %s, GitHub recorded %s' % (name, actual, expected))
                problem = kind_problem(name, path)
                if problem:
                    found.append('%s: %s' % (name, problem))
                print('%s %s  %s' % ('FAIL' if found else 'ok  ', actual, name), flush=True)
                problems += found
            finally:
                os.remove(path)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tag', help='e.g. v1.0.0-rc2')
    parser.add_argument('--repo', default=REPO)
    parser.add_argument('--no-download', action='store_true', help='Check the asset list only.')
    args = parser.parse_args(argv)

    release = fetch_release(args.tag, args.repo)
    problems = release_problems(args.tag, release)
    print('%s: %d assets, %s' % (args.tag, len(release.get('assets', [])), release.get('html_url', '')))
    if not args.no_download:
        problems += check_files(args.tag, args.repo, release)
    for problem in problems:
        print('PROBLEM: ' + problem)
    print('%d problem(s)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
