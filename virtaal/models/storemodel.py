#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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

import os
import logging

from virtaal.common import pan_app

from basemodel import BaseModel


def fix_indexes(stats, valid_units=None):
    """convert statsdb array to use model index instead of storage class index"""
    if valid_units is None:
        valid_units = stats['total']

    new_stats = {}
    if valid_units:
        valid_unit_indexes = dict([(uindex, index) for (index, uindex) in enumerate(valid_units)])
        # Adjust stats
        for key in stats:
            if key == 'extended':
                new_stats['extended'] = {}
                for estate in stats['extended']:
                    new_stats['extended'][estate] = [valid_unit_indexes[i] for i in stats['extended'][estate]]
                continue
            new_stats[key] = [valid_unit_indexes[i] for i in stats[key]]
    return new_stats


class StoreModel(BaseModel):
    """
    This model represents a translation store/file. It is basically a wrapper
    for the C{translate.storage.store} class. It is mostly based on the old
    C{Document} class from Virtaal's pre-MVC days.
    """

    __gtype_name__ = "StoreModel"

    # INITIALIZERS #
    def __init__(self, fileobj, controller):
        super(StoreModel, self).__init__()
        self.controller = controller
        self.load_file(fileobj)


    # SPECIAL METHODS #
    def __getitem__(self, index):
        """Alias for C{get_unit}."""
        return self.get_unit(index)

    def __len__(self):
        if not self._trans_store:
            return -1
        return len(self._valid_units)


    # ACCESSORS #
    def get_filename(self):
        return self._trans_store and self._trans_store.filename or None

    def get_checker(self):
        return self._checker

    def get_source_language(self):
        """Return the current store's source language."""
        candidate = self._trans_store.units[0].getsourcelanguage()
        # If we couldn't get the language from the first unit, try the store
        if candidate is None:
            candidate = self._trans_store.getsourcelanguage()
        if candidate and not candidate in ['und', 'en', 'en_US']:
            return candidate

    def set_source_language(self, langcode):
        self._trans_store.setsourcelanguage(langcode)

    def get_target_language(self):
        """Return the current store's target language."""
        candidate = self._trans_store.units[0].gettargetlanguage()
        # If we couldn't get the language from the first unit, try the store
        if candidate is None:
            candidate = self._trans_store.gettargetlanguage()
        if candidate and candidate != 'und':
            return candidate

    def set_target_language(self, langcode):
        self._trans_store.settargetlanguage(langcode)

    def get_store_type(self):
        return self._trans_store.Name

    def get_unit(self, index):
        """Get a specific unit by index."""
        return self._trans_store.units[self._valid_units[index]]

    def get_units(self):
        # TODO: Add caching
        """Return the current store's (filtered) units."""
        return [self._trans_store.units[i] for i in self._valid_units]

    def get_stats_totals(self):
        """Return totals for word and string counts."""
        if not self.filename:
            return {}
        from translate.storage import statsdb
        totals = statsdb.StatsCache().file_extended_totals(self.filename,  self._trans_store)
        return totals


    # METHODS #
    def load_file(self, fileobj):
        # Adapted from Document.__init__()
        filename = fileobj
        if isinstance(filename, basestring):
            if not os.path.exists(filename):
                raise IOError(_('The file does not exist.'))
            if not os.path.isfile(filename):
                raise IOError(_('Not a valid file.'))
        else:
            # Try and determine the file name of the file object
            filename = getattr(fileobj, 'name', None)
            if filename is None:
                filename = getattr(fileobj, 'filename', None)
            if filename is None:
                filename = '<projectfile>'
        logging.info('Loading file %s' % (filename))
        from translate.storage import factory
        self._trans_store = factory.getobject(fileobj)
        self.filename = filename
        self.update_stats(filename=filename)
        #self._correct_header(self._trans_store)
        self.nplurals = self._compute_nplurals(self._trans_store)

    def save_file(self, filename=None):
        self._update_header()
        if filename is None:
            filename = self.filename
        if filename == self.filename:
            self._trans_store.save()
        else:
            self._trans_store.savefile(filename)
        self.update_stats(filename=filename)

    def update_stats(self, filename=None):
        self.stats = None
        if self._trans_store is None:
            return

        if filename is None:
            filename = self.filename

        from translate.storage import statsdb
        stats = statsdb.StatsCache().filestatestats(filename,  self._trans_store, extended=True)
        self._valid_units = stats['total']
        self.stats = fix_indexes(stats)
        return self.stats

    def update_checks(self, checker=None, filename=None):
        self.checks = None
        if self._trans_store is None:
            return

        if filename is None:
            filename = self.filename

        if checker is None:
            checker = self._checker
        else:
            self._checker = checker

        from translate.storage import statsdb
        errors = statsdb.StatsCache().filechecks(filename, checker, self._trans_store)
        self.checks = fix_indexes(errors, self._valid_units)
        return self.checks

    def update_file(self, filename):
        # Adapted from Document.__init__()
        from translate.storage import factory, statsdb
        newstore = factory.getobject(filename)
        oldfilename = self._trans_store.filename
        oldfileobj = self._trans_store.fileobj

        #get a copy of old stats before we convert
        from translate.filters import checks
        oldstats = statsdb.StatsCache().filestats(oldfilename, checks.UnitChecker(), self._trans_store)

        from translate.convert import pot2po
        self._trans_store = pot2po.convert_stores(newstore, self._trans_store, fuzzymatching=False)
        self._trans_store.fileobj = oldfileobj #Let's attempt to keep the old file and name if possible

        #FIXME: ugly tempfile hack, can we please have a pure store implementation of statsdb
        import tempfile
        import os
        tempfd, tempfilename = tempfile.mkstemp()
        os.write(tempfd, str(self._trans_store))
        self.update_stats(filename=tempfilename)
        os.close(tempfd)
        os.remove(tempfilename)

        self.controller.compare_stats(oldstats, self.stats)

        # store filename or else save is confused
        self._trans_store.filename = oldfilename
        self._correct_header(self._trans_store)
        self.nplurals = self._compute_nplurals(self._trans_store)

    def _compute_nplurals(self, store):
        # Copied as-is from Document._compute_nplurals()
        # FIXME this needs to be pushed back into the stores, we don't want to import each format
        from translate.storage.poheader import poheader
        if isinstance(store, poheader):
            nplurals, _pluralequation = store.getheaderplural()
            if nplurals is None:
                return
            return int(nplurals)
        else:
            from translate.storage import ts2 as ts
            if isinstance(store, ts.tsfile):
                return store.nplural()

    def _correct_header(self, store):
        """This ensures that the file has a header if it is a poheader type of
        file, and fixes the statistics if we had to add a header."""
        # Copied as-is from Document._correct_header()
        from translate.storage.poheader import poheader
        if isinstance(store, poheader) and not store.header():
            store.updateheader(add=True)
            new_stats = {}
            for key, values in self.stats.iteritems():
                new_stats[key] = [value+1 for value in values]
            self.stats = new_stats

    def _update_header(self):
        """Make sure that headers are complete and update with current time (if applicable)."""
        # This method comes from Virtaal 0.2's main_window.py:Virtaal._on_file_save().
        # It makes sure that, if we are working with a PO file, that all header info is present.
        from translate.storage.poheader import poheader, tzstring
        if isinstance(self._trans_store, poheader):
            name = self.controller.main_controller.get_translator_name()
            email = self.controller.main_controller.get_translator_email()
            team = self.controller.main_controller.get_translator_team()
            if name is None or email is None or team is None:
                # User cancelled
                raise Exception('Save cancelled.')
            pan_app.settings.translator["name"] = name
            pan_app.settings.translator["email"] = email
            pan_app.settings.translator["team"] = team
            pan_app.settings.write()

            header_updates = {}
            import time
            header_updates["PO_Revision_Date"] = time.strftime("%Y-%m-%d %H:%M") + tzstring()
            header_updates["X_Generator"] = pan_app.x_generator
            if name or email:
                header_updates["Last_Translator"] = u"%s <%s>" % (name, email)
                self._trans_store.updatecontributor(name, email)
            if team:
                header_updates["Language-Team"] = team
            target_lang = self.controller.main_controller.lang_controller.target_lang
            header_updates["Language"] = target_lang.code
            project_code = self.controller.main_controller.checks_controller.code
            if project_code:
                header_updates["X-Project-Style"] = project_code
            self._trans_store.updateheader(add=True, **header_updates)

            plural = target_lang.plural
            nplurals = target_lang.nplurals
            if plural:
                self._trans_store.updateheaderplural(nplurals, plural)
