#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Save a translation store without risking the file already on disk."""

import errno
import io
import os
import secrets
import stat

# fsync() isn't supported on some network and FUSE file systems.
_FSYNC_UNSUPPORTED = {errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP}


def save_store(store, filename):
    """Write store to filename, as store.savefile(filename) does.

    The store is written to a hidden temporary file in the same folder,
    which then replaces the file, so a write that fails part-way leaves
    the old file whole (#4841). A symlink's target is replaced, not the
    link, and an existing file keeps its mode.

    The file is written in place instead, from the bytes already
    serialised, when it isn't a regular file or has other hard links or
    another owner, when no temporary file can be made beside it, or when
    it can't be replaced (on Windows, while another program has it
    open)."""
    target = os.path.realpath(filename)
    info = None
    if os.path.lexists(target):
        if os.path.isdir(target):
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), filename)
        # os.replace() would replace a read-only file on POSIX.
        if not os.access(target, os.W_OK):
            raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), filename)
        info = os.stat(target)

    if info is not None and (not stat.S_ISREG(info.st_mode) or info.st_nlink > 1
                             or _owned_by_someone_else(info)):
        _write_in_place(target, _serialize(store))
    else:
        _replace(store, target, info)
    store.fileobj = None
    store.filename = filename


def _owned_by_someone_else(info):
    return hasattr(os, 'geteuid') and info.st_uid != os.geteuid()


def _serialize(store):
    out = io.BytesIO()
    store.serialize(out)
    return out.getvalue()


def _open_temp(target, mode):
    """A new file beside target, created with mode (less the umask)."""
    folder, name = os.path.split(target)
    while True:
        path = os.path.join(folder, f'.{name}.virtaal-save-{secrets.token_hex(4)}')
        try:
            return open(path, 'xb', opener=lambda p, flags: os.open(p, flags, mode))
        except FileExistsError:
            continue


def _replace(store, target, info):
    try:
        # Owner-only until it has the existing file's mode.
        tmp = _open_temp(target, 0o666 if info is None else 0o600)
    except OSError:
        _write_in_place(target, _serialize(store))
        return
    try:
        with tmp:
            store.serialize(tmp)
            _flush(tmp)
        if info is not None:
            if hasattr(os, 'chown') and os.stat(tmp.name).st_gid != info.st_gid:
                try:
                    os.chown(tmp.name, -1, info.st_gid)
                except OSError:
                    pass
            try:
                os.chmod(tmp.name, stat.S_IMODE(info.st_mode))
            except OSError:
                pass
        try:
            os.replace(tmp.name, target)
        except OSError:
            with open(tmp.name, 'rb') as f:
                data = f.read()
            _write_in_place(target, data)
    finally:
        try:
            os.remove(tmp.name)
        except FileNotFoundError:
            pass
        except OSError:
            import logging
            logging.warning("Couldn't remove %r", tmp.name)


def _write_in_place(target, data):
    with open(target, 'wb') as f:
        f.write(data)
        _flush(f)


def _flush(f):
    f.flush()
    try:
        os.fsync(f.fileno())
    except OSError as e:
        if e.errno not in _FSYNC_UNSUPPORTED:
            raise
