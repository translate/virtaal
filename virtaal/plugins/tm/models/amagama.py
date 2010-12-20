#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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

import remotetm


class TMModel(remotetm.TMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'AmagamaTMModel'
    display_name = _('Amagama')
    description = _('Previous translations for Free and Open Source Software')
    #l10n: Try to keep this as short as possible.
    shortname = _('Amagama')

    default_config = {
        "host" : "amagama.locamotion.org",
        "port" : "80",
    }

    def push_store(self, store_controller):
        pass

    def upload_store(self, store_controller):
        pass
