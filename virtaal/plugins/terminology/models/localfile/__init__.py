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
import os
from translate.search.match import terminologymatcher
from translate.storage.placeables.terminology import TerminologyPlaceable
from translate.storage import factory

#FIXME: The following line will cause this model to not work if plug-ins are loaded from ~/.virtaal/virtaal_plugins (probably)
from virtaal.plugins.terminology.models.basetermmodel import BaseTerminologyModel

from localfileview import LocalFileView


class TerminologyModel(BaseTerminologyModel):
    """
    Terminology model that loads terminology from a PO file on the local filesystem.
    """

    __gtype_name__ = 'LocalFileTerminologyModel'
    description = _('Use a local translation file as terminology source.')
    display_name = _('Local file')

    default_config = { 'files': '' }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TerminologyModel, self).__init__(controller)

        self.matcher = None
        self.internal_name = internal_name
        self.stores = []

        self.load_config()
        self.load_files()
        self.view = LocalFileView(self)


    # METHODS #
    def destroy(self):
        self.view.destroy()
        self.save_config()
        super(TerminologyModel, self).destroy()
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

    def get_extend_store(self):
        extendfile = self.config['extendfile']
        for store in self.stores:
            if os.path.abspath(getattr(store, 'filename', '')) == os.path.abspath(extendfile):
                return store
        return None

    def load_config(self):
        super(TerminologyModel, self).load_config()
        self.config['files'] = self.config['files'].split(',')

    def load_files(self):
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

        self.stores = []
        for filename in self.config['files']:
            if not filename:
                continue
            if not os.path.isfile(filename):
                logging.debug('Not a file: "%s"' % (filename))
                continue
            self.stores.append(factory.getobject(filename))
        self.matcher = terminologymatcher(self.stores)
        TerminologyPlaceable.matchers.append(self.matcher)
