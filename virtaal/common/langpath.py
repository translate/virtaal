#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""File and folder names built from language codes."""

import os
import re

_CODE_RE = re.compile(r'[A-Za-z0-9_@.-]{1,64}')

# Names Windows reserves for devices, with or without an extension.
_RESERVED_NAMES = frozenset(
    ['con', 'prn', 'aux', 'nul']
    + ['com%d' % i for i in range(1, 10)]
    + ['lpt%d' % i for i in range(1, 10)])


def is_safe_lang_code(code):
    """Whether code can be part of a file or folder name.

        A file can declare any language code, and LanguageModel keeps
        codes it doesn't know unchanged."""
    return (isinstance(code, str) and _CODE_RE.fullmatch(code) is not None
            and not code.startswith('.') and not code.endswith('.') and '..' not in code)


def lang_folder_name(code):
    """The name of the folder for a safe language code. Codes that are
        Windows device names ("con" is Cofán) get a "_" after the
        name, on every platform."""
    stem, dot, rest = code.partition('.')
    if stem.lower() in _RESERVED_NAMES:
        return stem + '_' + dot + rest
    return code


def path_inside(directory, *names):
    """os.path.join(directory, *names), or None if that resolves to
        directory itself or anywhere outside it."""
    path = os.path.join(directory, *names)
    root = os.path.realpath(directory)
    real = os.path.realpath(path)
    try:
        if real == root or os.path.commonpath([root, real]) != root:
            return None
    except ValueError:
        # Different drives on Windows.
        return None
    return path
