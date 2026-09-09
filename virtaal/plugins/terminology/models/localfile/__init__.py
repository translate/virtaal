#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os

from translate.search.match import terminologymatcher
from translate.storage import factory
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.common import pan_app

try:
    from virtaal.plugins.terminology.models.basetermmodel import BaseTerminologyModel
except ImportError:
    from virtaal_plugins.terminology.models.basetermmodel import BaseTerminologyModel

from .localfileview import LocalFileView


class TerminologyModel(BaseTerminologyModel):
    """
    Terminology model that loads terminology from a PO file on the local filesystem.
    """

    __gtype_name__ = 'LocalFileTerminologyModel'
    display_name = _('Local Files')
    description = _('Local terminology files')

    default_config = {
        'extendfile': os.path.join(pan_app.get_config_dir(), 'terminology.po'),
        'files': ''
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super().__init__(controller)

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
        super().destroy()
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

    def get_duplicates(self, src_text, tgt_text):
        base_src_text = src_text.strip()
        base_tgt_text = tgt_text.strip()
        units = []
        for store in self.stores:
            for unit in store.units:
                if unit.source.strip() == base_src_text and \
                        unit.target.strip() == base_tgt_text:
                    return True
        return False

    def get_extend_store(self):
        extendfile = self.config['extendfile']
        for store in self.stores:
            if os.path.abspath(getattr(store, 'filename', '')) == os.path.abspath(extendfile):
                return store
        return None

    def get_store_for_filename(self, filename):
        for store in self.stores:
            if os.path.abspath(getattr(store, 'filename', '')) == os.path.abspath(filename):
                return store
        return None

    def get_units_with_source(self, src_text):
        stripped_src_text = src_text.strip().lower()
        units = []
        for store in self.stores:
            for unit in store.units:
                if unit.source.strip().lower() == stripped_src_text:
                    units.append(unit)
        return units

    def load_config(self):
        super().load_config()
        conffiles = []
        for filename in self.config['files'].split(','):
            if os.path.exists(filename):
                conffiles.append(filename)
        self.config['files'] = conffiles

        if not os.path.exists(self.config['extendfile']) and len(self.config['files']) > 0:
            self.config['extendfile'] = self.config['files'][0]

        if not os.path.exists(self.config['extendfile']):
            self.config['extendfile'] = self.default_config['extendfile']

        if not self.config['extendfile'] in self.config['files']:
            self.config['files'].append(self.config['extendfile'])

    def load_files(self):
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

        self.stores = []
        for filename in self.config['files']:
            if not filename:
                continue
            if not os.path.isfile(filename):
                logging.debug('Not a file: "%s"' % (filename))
            self.stores.append(factory.getobject(filename))
        self.matcher = terminologymatcher(self.stores)
        TerminologyPlaceable.matchers.append(self.matcher)
