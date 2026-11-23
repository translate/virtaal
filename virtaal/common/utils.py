#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

def get_bytes(string):
    if isinstance(string, str):
        return string.encode()
    return string


def path_from_file_uri(uri):
    """The local path a file:// URI names, %-escapes decoded.

    A URI GLib rejects (an unescaped %) keeps the path part as given."""
    from gi.repository import GLib

    from virtaal.common.platform import platform
    try:
        return GLib.filename_from_uri(uri)[0]
    except GLib.Error:
        path = uri[len('file://'):]
        if path[:len('localhost/')].lower() == 'localhost/':
            path = path[len('localhost'):]
        if platform.is_windows:
            path = path[1:]
        return path
