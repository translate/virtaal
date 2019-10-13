import sys

from six import text_type


def get_unicode(string, encoding=None):
    if isinstance(string, text_type):
        return string
    return string.decode(encoding or sys.getfilesystemencoding())


def get_bytes(string):
    if isinstance(string, text_type):
        return string.encode()
    return string
