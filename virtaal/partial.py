#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2008 Zuza Software Foundation
# 
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

def partial(f, *args, **kwargs):
    def new_f(*new_args, **new_kwargs):
        all_args = args + new_args
        kwargs.update(new_kwargs)
        return f(*all_args, **kwargs)
    
    for attr in ('__module__', '__name__', '__doc__'):
        setattr(new_f, attr, getattr(f, attr))
    for attr in ('__dict__',):
        getattr(new_f, attr).update(getattr(f, attr, {}))
 
    return new_f

