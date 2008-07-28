#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# VirTaal is free software; you can redistribute it and/or modify
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

__all__ = ['get_terminology_directory', 
           'get_suggestion_store', 
           'set_terminology_directory']

import os
import os.path as path

from translate.storage import factory

from pan_app import settings
from support.memoize import memoize, invalidates_memoization

def add_to_store(unit_dict, unit_builder, store):
    for unit in store.units:
        key = unicode(unit.source)
        if key not in unit_dict:
            unit_dict[key] = unit_builder(unit)

def get_terminology_directory():
    return settings.general["termininology-dir"]

@memoize
def get_suggestion_store(lang_code):
    store = factory.getclass("tmp.po")()
    unit_dict = {}
    for base, _dirnames, filenames in os.walk(path.join(get_terminology_directory(), lang_code)):
        for filename in filenames:
            try:
                add_to_store(unit_dict, store.UnitClass.buildfromunit, factory.getobject(path.join(base, filename)))
            except ValueError:
                pass
    for unit in unit_dict.itervalues():
        store.addunit(unit)
    return store

@invalidates_memoization(get_suggestion_store)
def set_terminology_directory(directory):
    settings.general["termininology-dir"] = directory
    
