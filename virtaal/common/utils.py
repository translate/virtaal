import sys



def get_unicode(string, encoding=None):
    if isinstance(string, str):
        return string
    return string.decode(encoding or sys.getfilesystemencoding())


def get_bytes(string):
    if isinstance(string, str):
        return string.encode()
    return string
