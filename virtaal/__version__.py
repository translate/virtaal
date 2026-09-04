#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""This file contains the version."""
ver = "1.0.0-beta1"


def _get_build_commit():
    """The git commit this build was made from, or None if that's not
    knowable.

    Two sources, tried in order:

    1. virtaal._build_info, a plain "commit = '<sha>'" file the
       packaging scripts (devsupport/packaging/*/build_standalone.*)
       generate fresh just before running PyInstaller - not checked
       into git (see .gitignore). The only source that works in a
       frozen build, which has no .git directory or git binary.
    2. A live `git rev-parse HEAD`, for everything else (running from
       a checkout directly, e.g. bin/virtaal or the run-virtaal
       skill).
    """
    try:
        from virtaal._build_info import commit
        return commit
    except ImportError:
        pass
    try:
        import subprocess
        from os import path
        repo_root = path.dirname(path.dirname(path.abspath(__file__)))
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=repo_root,
            capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


build_commit = _get_build_commit()
