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


def write_file_atomically(path, data):
    """Write data (bytes) to path through a temporary file in the same
    folder, so a failed write (a full disk) leaves no partial file and
    any existing one unchanged. The temporary name starts with a dot, so
    a folder scan by name or extension never picks it up. A new file is
    readable only by its owner; an existing one keeps its mode, and a
    read-only one is not replaced. A symlink's target is written. Raises
    OSError."""
    import os
    import stat
    import tempfile
    path = os.path.realpath(path)
    mode = None
    if os.path.exists(path):
        if not os.access(path, os.W_OK):
            raise PermissionError(f"{path!r} is read-only")
        mode = stat.S_IMODE(os.stat(path).st_mode)
    folder, name = os.path.split(path)
    fd, tmp = tempfile.mkstemp(dir=folder or '.', prefix='.' + name + '.', suffix='.tmp')
    try:
        # Write through mkstemp's own descriptor: reopening tmp by name
        # could follow something swapped in at that name meanwhile.
        with open(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
