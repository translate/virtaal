#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
# Copyright 2013 F Wolff
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

from gtk import Builder

from virtaal.common import pan_app


#cache builders so that we don't parse files repeatedly
_builders = {}


class BaseView(object):
    """Interface for views."""

    def __init__(self):
        raise NotImplementedError('This interface cannot be instantiated.')

    @classmethod
    def load_builder_file(cls, path_parts, root=None, domain=''):
        _id = "/".join(path_parts)
        if _id in _builders:
            return _builders[_id]
        buildername = pan_app.get_abs_data_filename(path_parts)
        builder = Builder()
        builder.add_from_file(buildername)
        builder.set_translation_domain(domain)
        _builders[_id] = builder
        return builder

    def show(self):
        raise NotImplementedError('This method needs to be implemented by all sub-classes.')
