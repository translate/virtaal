#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.



def debug_func(f):
    """Function decorator to start a pdb shell before calling the decorated
        function."""
    def debuggedf(*args, **kwargs):
        import pdb
        pdb.set_trace()
        return f(*args, **kwargs)
    return debuggedf

def log_args(fn, classname=None):
    """Function decorator that logs the call of the decorated function with
        arguments and return value."""
    if classname is None:
        classname = ''
    else:
        classname = classname + '.'

    def logger_fn(*args, **kwargs):
        args_s = ', '.join([repr(a) for a in args])
        kwargs_s = ', '.join(("%s=%s" % (key, repr(value))) for key, value in kwargs.items())
        if not args_s or not kwargs_s:
            all_args = args_s + kwargs_s
        else:
            all_args = ', '.join([args_s, kwargs_s])
        retval = fn(*args, **kwargs)
        print('%s%s(%s) => %s' % (classname, fn.__name__, all_args, retval))
        return retval

    return logger_fn

def log_all_methods(cls):
    """Class decorator that applies the C{log_args} decorator to all of the
        methods in the class."""
    if not hasattr(cls, '__base__'):
        raise TypeError('Not a class: %s' % (cls))
    for attr in dir(cls):
        method = getattr(cls, attr)
        if attr.startswith('__') and attr.endswith('__') or getattr(method, 'im_class', None) is not cls:
            continue
        if callable(method):
            setattr(cls, attr, log_args(method, classname=cls.__name__))
    return cls
