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

__all__ = ['get_terminology_matcher', 
           'set_terminology_directory']

import os
import os.path as path

from translate.storage import factory

import pan_app
from support.memoize import memoize, invalidates_memoization
from translate.search import match

def get_terminology_directory():
    return pan_app.settings.general["terminology-dir"]

def get_suggestion_stores(lang_code):
    """Return a suggestion store which is an amalgamation of all the translation
    stores under <termininology_directory>/<lang_code>."""
    for base, _dirnames, filenames in os.walk(path.join(get_terminology_directory(), lang_code)):
        for filename in filenames:
            try: # Try to load filename as a translation store...
                yield factory.getobject(path.join(base, filename))
            except ValueError: # If filename isn't a translation store, we just do nothing
                pass

@memoize
def get_terminology_matcher(lang_code):
    """Return a terminology matcher based on a translation store which is an
    amalgamation of all translation stores under 
    <termininology_directory>/<lang_code>
    
    <termininology_directory> is the globally specified termininology directory.
    <lang_code> is the supplied parameter.
    
    @return: a translate.search.match.terminologymatcher"""
    return match.terminologymatcher(list(get_suggestion_stores(pan_app.settings.language["contentlang"])))

@invalidates_memoization(get_terminology_matcher)
def set_terminology_directory(directory):
    pan_app.settings.general["terminology-dir"] = directory
    
