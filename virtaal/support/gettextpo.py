#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The checks of ``msgfmt -c``, run on single units through libgettextpo.

libgettextpo's po_message_check_all() checks format strings according
to the ``*-format`` flags, plural forms against the header's
Plural-Forms, leading/trailing newlines and the header itself.
"""

import ctypes
import ctypes.util
import logging
import os

from translate.filters.decorators import Category

from virtaal.common.platform import platform

_xerror_prototype = ctypes.CFUNCTYPE(
    None,
    ctypes.c_int, ctypes.c_void_p,
    ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_int, ctypes.c_char_p,
)
_xerror2_prototype = ctypes.CFUNCTYPE(
    None,
    ctypes.c_int, ctypes.c_void_p,
    ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_int, ctypes.c_char_p,
    ctypes.c_void_p,
    ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_int, ctypes.c_char_p,
)


class _XErrorHandler(ctypes.Structure):
    _fields_ = [
        ('xerror', _xerror_prototype),
        ('xerror2', _xerror2_prototype),
    ]


_LIBRARY_NAMES = ('libgettextpo.0.dylib', 'libgettextpo.dylib', 'libgettextpo-0.dll', 'libgettextpo.so.0')

_SIGNATURES = {
    'po_file_create': ([], ctypes.c_void_p),
    'po_file_free': ([ctypes.c_void_p], None),
    'po_message_iterator': ([ctypes.c_void_p, ctypes.c_char_p], ctypes.c_void_p),
    'po_message_iterator_free': ([ctypes.c_void_p], None),
    'po_message_insert': ([ctypes.c_void_p, ctypes.c_void_p], None),
    'po_message_create': ([], ctypes.c_void_p),
    'po_message_set_msgctxt': ([ctypes.c_void_p, ctypes.c_char_p], None),
    'po_message_set_msgid': ([ctypes.c_void_p, ctypes.c_char_p], None),
    'po_message_set_msgid_plural': ([ctypes.c_void_p, ctypes.c_char_p], None),
    'po_message_set_msgstr': ([ctypes.c_void_p, ctypes.c_char_p], None),
    'po_message_set_msgstr_plural': ([ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p], None),
    'po_message_set_format': ([ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int], None),
    'po_message_check_all': ([ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_XErrorHandler)], None),
}

_lib = None
_load_attempted = False


def _library_candidates():
    # A frozen build's own copy first: find_library() only searches
    # system paths, so it could pick up e.g. Homebrew's instead.
    if platform.is_frozen and platform.bundle_dir:
        for directory in (platform.bundle_dir,
                          os.path.join(platform.bundle_dir, '_internal'),
                          os.path.join(os.path.dirname(platform.bundle_dir), 'Frameworks')):
            for name in _LIBRARY_NAMES:
                path = os.path.join(directory, name)
                if os.path.isfile(path):
                    yield path
    found = ctypes.util.find_library('gettextpo')
    if found:
        yield found
    yield from _LIBRARY_NAMES


def _load_library():
    global _lib, _load_attempted
    if _load_attempted:
        return _lib
    _load_attempted = True

    for name in _library_candidates():
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        try:
            for funcname, (argtypes, restype) in _SIGNATURES.items():
                func = getattr(lib, funcname)
                func.argtypes = argtypes
                func.restype = restype
        except AttributeError as e:
            logging.debug('%s lacks %s', name, e)
            continue
        _lib = lib
        return _lib
    logging.debug('libgettextpo not found; msgfmt checks disabled')
    return None


def available():
    """Whether libgettextpo could be loaded."""
    return _load_library() is not None


def _encode(text):
    return str(text).encode('utf-8')


def _strings(multistring):
    strings = getattr(multistring, 'strings', None)
    if strings is None:
        return [multistring]
    return [str(s) for s in strings]


def _unit_flags(unit):
    flags = []
    for comment in getattr(unit, 'typecomments', []):
        comment = comment.strip()
        if comment.startswith('#,'):
            comment = comment[2:]
        flags.extend(f.strip() for f in comment.split(','))
    return [f for f in flags if f]


class MsgfmtChecker:
    """Checks single units like ``msgfmt -c`` would.

    Holds an in-memory PO file with only the store's header, so plurals
    are checked against its Plural-Forms."""

    def __init__(self):
        self._lib = _load_library()
        if self._lib is None:
            raise RuntimeError('libgettextpo is not available')
        self._file = None
        self._iterator = None
        self._header = None
        self._message = None
        self._problems = None

        # Referenced here so the callbacks aren't garbage collected.
        self._xerror = _xerror_prototype(self._on_xerror)
        self._xerror2 = _xerror2_prototype(self._on_xerror2)
        self._handler = _XErrorHandler(self._xerror, self._xerror2)

    def __del__(self):
        self._free()

    def _free(self):
        if self._iterator:
            self._lib.po_message_iterator_free(self._iterator)
            self._iterator = None
        if self._file:
            self._lib.po_file_free(self._file)
            self._file = None

    def set_header(self, header):
        """Set the header (the header entry's msgstr) to check against."""
        header = str(header or '')
        if header == self._header and self._file:
            return
        self._free()
        lib = self._lib
        self._header = header
        self._file = lib.po_file_create()
        self._iterator = lib.po_message_iterator(self._file, None)
        message = lib.po_message_create()
        lib.po_message_set_msgid(message, b'')
        lib.po_message_set_msgstr(message, _encode(header))
        lib.po_message_insert(self._iterator, message)

    def _on_xerror(self, severity, message, filename, lineno, column, multiline, text):
        # po_message_check_all() also checks the header in our file every
        # time; only report problems in the message being checked.
        if message and message != self._message:
            return
        self._add_problem(text)

    def _on_xerror2(self, severity, message1, filename1, lineno1, column1, multiline1, text1,
                    message2, filename2, lineno2, column2, multiline2, text2):
        texts = ((text1 or b'').rstrip(), (text2 or b'').strip())
        self._add_problem(b' '.join(t for t in texts if t))

    def _add_problem(self, text):
        # Severity is ignored: the checking API reports errors and
        # warnings, never fatal errors (which must not return).
        if self._problems is None:
            return
        text = (text or b'').decode('utf-8', 'replace').strip()
        if text:
            self._problems.append(text)

    def _make_message(self, unit):
        lib = self._lib
        message = lib.po_message_create()
        sources = _strings(unit.source)
        targets = _strings(unit.target)

        context = unit.getcontext()
        if context:
            lib.po_message_set_msgctxt(message, _encode(context))
        lib.po_message_set_msgid(message, _encode(sources[0]))
        if unit.hasplural() and len(sources) > 1:
            lib.po_message_set_msgid_plural(message, _encode(sources[1]))
            for i, target in enumerate(targets):
                lib.po_message_set_msgstr_plural(message, i, _encode(target))
        else:
            lib.po_message_set_msgstr(message, _encode(targets[0] if targets else ''))

        # Not marked fuzzy: libgettextpo skips format checks on fuzzy
        # messages, and a fuzzy unit is usually the one being edited.
        for flag in _unit_flags(unit):
            if flag.endswith('-format'):
                is_format = not flag.startswith('no-')
                format_type = flag if is_format else flag[len('no-'):]
                lib.po_message_set_format(message, _encode(format_type), int(is_format))
        return message

    def check_unit(self, unit):
        """The problems ``msgfmt -c`` reports for unit, as strings.

        Untranslated units are skipped, as msgfmt does."""
        if unit.isheader():
            self.set_header(_strings(unit.target)[0])
        elif not any(_strings(unit.target)):
            return []
        if self._file is None:
            self.set_header('')

        # Not inserted into our file, which would keep it alive with the
        # file. libgettextpo has no po_message_free(), so it leaks.
        self._message = self._make_message(unit)
        self._problems = []
        try:
            self._lib.po_message_check_all(self._message, self._iterator, ctypes.byref(self._handler))
            return self._problems
        finally:
            self._message = None
            self._problems = None



class MsgfmtCheck:
    """The "msgfmt" extra check: the problems ``msgfmt -c`` reports."""

    name = 'msgfmt'
    category = Category.CRITICAL

    @staticmethod
    def applies_to(store):
        from translate.storage import pypo
        return isinstance(store, pypo.pofile)

    @staticmethod
    def available():
        return available()

    def __init__(self):
        self._checker = MsgfmtChecker()

    def check(self, unit):
        store = getattr(unit, '_store', None)
        header = store.header() if store is not None else None
        self._checker.set_header(header.target if header is not None else '')
        return '\n'.join(self._checker.check_unit(unit)) or None
