#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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

import logging


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
        print '%s%s(%s) => %s' % (classname, fn.__name__, all_args, retval)
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
