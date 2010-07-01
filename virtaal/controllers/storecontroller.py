#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
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

import gobject
import logging
import os
import re
from tempfile import mkstemp
from translate.convert import factory as convert_factory
from translate.storage import proj

from virtaal.common import GObjectWrapper
from virtaal.models import StoreModel
from virtaal.views import StoreView
from basecontroller import BaseController
from cursor import Cursor


# TODO: Create an event that is emitted when a cursor is created
class StoreController(BaseController):
    """The controller for all store-level activities."""

    __gtype_name__ = 'StoreController'
    __gsignals__ = {
        'store-loaded': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        'store-saved':  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        'store-closed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.store_controller = self
        self._unit_controller = None # This is set by UnitController itself when it is created

        self._archivetemp = None
        self.cursor = None
        self.handler_ids = {}
        self._modified = False
        self.project = None
        self.store = None
        self._tempfiles = []
        self.view = StoreView(self)

        self._controller_register_id = self.main_controller.connect('controller-registered', self._on_controller_registered)

    def destroy(self):
        if self.project:
            del self.project
        if self._archivetemp and os.path.isfile(self._archivetemp):
            os.unlink(self._archivetemp)
        for tempfile in self._tempfiles:
            try:
                os.unlink(tempfile)
            except Exception:
                pass


    # ACCESSORS #
    def get_nplurals(self, store=None):
        if not store:
            store = self.store
        return store and store.nplurals or 0

    def get_bundle_filename(self):
        """Returns the file name of the bundle archive, if we are working with one."""
        if self.project and isinstance(self.project.store, proj.BundleProjectStore):
            return self.project.store.zip.filename
        return None

    def get_store(self):
        return self.store

    def get_store_filename(self):
        """Returns a display-friendly string representing the current open
            store's file name. If a bundle is currently open, this method will
            return a file name in the format "bundle.zip:some_file.xlf"."""
        store = self.get_store()
        if not store:
            return ''
        filename = ''
        if self.project:
            if isinstance(self.project.store, proj.BundleProjectStore):
                # This should always be the case
                filename = self.project.store.zip.filename + ':'
                projfname = self.project.get_proj_filename(store.get_filename())
                _dir, projfname = os.path.split(projfname)
                filename += projfname
        else:
            filename += store.get_filename()
        return filename

    def get_store_checker(self):
        store = self.get_store()
        if not store:
            raise ValueError('No store to get checker from')
        return store.get_checker()

    def get_store_stats(self):
        store = self.get_store()
        if not store:
            raise ValueError('No store to get checker from')
        return store.stats

    def get_unit_celleditor(self, unit):
        """Load the given unit in via the C{UnitController} and return
            the C{gtk.CellEditable} it creates."""
        return self.unit_controller.load_unit(unit)

    def is_modified(self):
        return self._modified

    def _get_unitcontroller(self):
        return self._unit_controller
    def _set_unitcontroller(self, unitcont):
        """@type unitcont: UnitController"""
        if self.unit_controller and 'unitview.unit-modified' in self.handler_ids:
            self.unit_controller.disconnect(self.handler_ids['unitview.unit-modified'])
        self._unit_controller = unitcont
        self.handler_ids['unitview.unit-modified'] = self.unit_controller.connect('unit-modified', self._unit_modified)
    unit_controller = property(_get_unitcontroller, _set_unitcontroller)


    # METHODS #
    def select_unit(self, unit, force=False):
        """Select the specified unit and scroll to it.
            Note that, because we change units via the cursor, the unit to
            select must be valid according to the cursor."""
        if self.cursor.deref() == unit and not force:
            # Unit is already selected; no need to do more work
            return

        i = 0
        try:
            i = self.store.get_units().index(unit)
        except Exception, exc:
            logging.debug('Unit not found:\n%s' % (exc))

        if force:
            self.cursor.force_index(i)
        else:
            self.cursor.index = i

    def open_file(self, filename, uri=''):
        force_saveas = False
        extension = filename.split(os.extsep)[-1]
        if extension == 'zip':
            try:
                self.project = proj.Project(proj.BundleProjectStore(filename))
            except proj.InvalidBundleError, err:
                logging.exception('Unable to load project bundle')

            if not len(self.project.store.transfiles):
                # FIXME: Ask the user to select a source file to convert?
                if not len(self.project.store.sourcefiles):
                    raise proj.InvalidBundleError(_('No source or translatable files in bundle'))
                self.project.convert_forward(self.project.store.sourcefiles[0])

            # FIXME: Ask the user which translatable file to open?
            transfile = self.project.get_file(self.project.store.transfiles[0])
            self.real_filename = transfile.name
            logging.info(
                'Editing translation file %s:%s' %
                (filename, self.project.store.transfiles[0])
            )
            self.store = StoreModel(transfile, self)
        elif extension in convert_factory.converters:
            # Use temporary file name for bundle archive
            tempfname = self._get_new_bundle_filename(filename)
            self._archivetemp = tempfname

            self.project = proj.Project(projstore=proj.BundleProjectStore(tempfname))
            srcfile, srcfilename, transfile, transfilename = self.project.add_source_convert(filename)
            self.real_filename = transfile.name

            logging.info('Converted document %s to translatable file %s' % (srcfilename, self.real_filename))
            self.store = StoreModel(transfile, self)
            force_saveas = True
        else:
            self.store = StoreModel(filename, self)

        if len(self.store.get_units()) < 1:
            raise ValueError(_('The file contains nothing to translate.'))

        self._modified = False

        # if file is a template force saveas
        pot_regexp = re.compile("\.pot(\.gz|\.bz2)?$")
        if pot_regexp.search(filename):
            force_saveas = True
            self.store._trans_store.filename = pot_regexp.sub('.po', filename)

        self.main_controller.set_force_saveas(force_saveas)
        self.main_controller.set_saveable(self._modified)

        self.cursor = Cursor(self.store, self.store.stats['total'])

        self.view.load_store(self.store)
        self.view.show()

        self.emit('store-loaded')

    def save_file(self, filename=None):
        if self.project is None:
            self.store.save_file(filename) # store.save_file() will raise an appropriate exception if necessary
        else:
            # XXX: filename is the name that the bundle archive should be saved
            #      as, seeing as self.store is opened from a temporary file
            #      (see translate.storage.bundleprojstore.BundleProjectStore.get_file())
            self.store.save_file()

            proj_fname = self.project.get_proj_filename(self.real_filename)
            if not proj_fname:
                # This really shouldn't happen
                raise ValueError("Unable to determine file's project name: %s" % (self.real_filename))

            self.project.update_file(proj_fname, open(self.real_filename))
            self.project.convert_forward(proj_fname, overwrite_output=True)
            self.project.save()

            if self._archivetemp:
                if self._archivetemp == filename:
                    self._archivetemp = None
                else:
                    assert self.project.store.zip.filename == self._archivetemp
                    self.project.close()
                    self.project = None
                    os.rename(self._archivetemp, filename)
                    self._archivetemp = None

                    cursor_pos = self.cursor.pos
                    def post_save(sender):
                        if not hasattr(self, '_proj_file_saved_id'):
                            return
                        self.disconnect(self._proj_file_saved_id)
                        self.main_controller.open_file(filename)
                        self.cursor.pos = cursor_pos
                    self._proj_file_saved_id = self.connect('store-saved', post_save)
        self._modified = False
        self.main_controller.set_saveable(False)
        self.emit('store-saved')

    def close_file(self):
        del self.project
        self.project = None
        self.store = None
        self._modified = False
        self.main_controller.set_saveable(False)
        self.view.hide() # This MUST be called BEFORE `self.cursor = None`
        self.emit('store-closed') # This should be emitted BEFORE `self.cursor = None` to allow any other modules to disconnect from the cursor
        self.cursor = None

    def export_project_file(self, filename=None, openafter=False, readonly=False):
        if not self.project:
            return
        if self.is_modified():
            self.main_controller.save_file()
        self.project.save()

        # Make sure we have an output file to export
        export_projfname = None
        if self.project.store.targetfiles:
            export_projfname = self.project.store.targetfiles[0]
        elif self.project.store.transfiles:
            transfile = self.project.store.transfiles[0]
            _export_file, export_projfname = self.project.convert_forward(transfile)

        if not export_projfname:
            raise RuntimeError("Unable to find an exportable file in project")

        if not filename:
            if readonly:
                # Read-only files to in the temp directory with a different
                # layout of its filename.
                fname, ext = proj.split_extensions(export_projfname.split('/')[-1])
                fname = 'virtaal_preview_' + fname + '_'
                ext = os.extsep + ext
                fd, filename = mkstemp(suffix=ext, prefix=fname)
                os.close(fd)
                self._tempfiles.append(filename)
            else:
                filename = self._guess_export_filename(export_projfname)

        logging.debug('Exporting project file %s to %s' % (export_projfname, filename))
        self.project.export_file(export_projfname, filename)

        if readonly:
            logging.debug('Setting %s read-only' % (filename))
            from stat import S_IREAD
            os.chmod(filename, S_IREAD)

        if openafter:
            logging.debug('Opening: %s' % (filename))
            from virtaal.support import openmailto
            openmailto.open(filename)

    def revert_file(self):
        self.open_file(self.store.filename)

    def update_file(self, filename, uri=''):
        if not self.store:
            #FIXME: we should never allow updates if no file is already open
            self.open_file(filename, uri=uri)
            return

        post_update_action = None
        extension = filename.split(os.extsep)[-1]
        if extension in convert_factory.converters:
            from translate.storage import factory
            try:
                outfile = convert_factory.convert(open(filename))[0]
                factory.getobject(outfile.name)
                filename = outfile.name
                def unlink_outfile():
                    try:
                        os.unlink(filename)
                    except Exception:
                        logging.exception("Unable to delete file %s:" % (filename))
            except Exception:
                # Anticipated exceptions/errors:
                # * Conversion error: anything that went wrong in
                #   convert_factory.convert(). This is likely if filename is a
                #   translation store that needs a template to be converted by
                #   the (automatically) selected converter.
                # * AttributeError on "outfile.name": if outfile is not a file-
                #   like object (with a "name" attribute)
                # * ValueError on factory.getobject(): outfile is not a
                #   translation store. This will happen when filename already
                #   refers to a translation store and we just converted it to
                #   a non-translation store format. FIXME: This might indicate
                #   a problem with the convert_factory not distinguising between
                #   its input and output document types.
                logging.exception("Error converting file to translatable file:")
        self.store.update_file(filename)

        self._modified = True
        self.main_controller.set_saveable(self._modified)
        self.main_controller.set_force_saveas(self._modified)

        self.cursor = Cursor(self.store, self.store.stats['total'])

        self.view.load_store(self.store)
        self.view.show()

        self.emit('store-loaded')

    def update_store_stats(self, **kwargs):
        """Shortcut to C{StoreModel.update_stats()}"""
        store = self.get_store()
        if not store:
            raise ValueError('No store to get checker from')
        return store.update_stats(**kwargs)

    def compare_stats(self, oldstats, newstats):
        #l10n: The heading of statistics before updating to the new template
        before = _("Before:")
        #l10n: The heading of statistics after updating to the new template
        after = _("After:")
        translated = _("Translated: %d")
        fuzzy = _("Fuzzy: %d")
        untranslated = _("Untranslated: %d")
        total = _("Total: %d")
        output = "%s\n\t%s\n\t%s\n\t%s\n\t%s\n" % (before, translated, fuzzy, untranslated, total)
        output += "%s\n\t%s\n\t%s\n\t%s\n\t%s" % (after, translated, fuzzy, untranslated, total)

        old_trans = len(oldstats['translated'])
        old_fuzzy = len(oldstats['fuzzy'])
        old_untrans = len(oldstats['untranslated'])
        old_total = old_trans + old_fuzzy + old_untrans

        new_trans = len(newstats['translated'])
        new_fuzzy = len(newstats['fuzzy'])
        new_untrans = len(newstats['untranslated'])
        new_total = new_trans + new_fuzzy + new_untrans

        output %= (old_trans, old_fuzzy, old_untrans, old_total,
                   new_trans, new_fuzzy, new_untrans, new_total)

        #l10n: this refers to updating a file to a new template (POT file)
        self.main_controller.show_info(_("File Updated"), output)

    def _get_new_bundle_filename(self, infilename):
        """Creates a file name that can be used for a bundle, based on the given
            file name.

            First tries to create a bundle in the same directory as the given
            file by the transformation in the following example:
            C{foo.odt -> foo_en__af.zip}
            where "en" and "af" are the currently selected source and target
            languages.

            If a with that name already exists, an attempt will be made to
            create a file name in the format C{foo_en__af_XXXXX.zip} in the
            document's directory. If that fails (the directory might not be
            writable), a temporary file name of the same format is created.

            @returns: The suggested file name for the bundle."""
        fname, extensions = proj.split_extensions(infilename)

        prefix = fname + u'_%s__%s' % (
            self.main_controller.lang_controller.source_lang.code,
            self.main_controller.lang_controller.target_lang.code
        )
        if extensions:
            extensions_parts = extensions.split(os.extsep)
            extensions_parts[-1] = u'zip'
            suffix = os.extsep.join([''] + extensions_parts)
        else:
            suffix = os.extsep + u'zip'

        # Try foo_en__af.zip
        outfname = prefix + suffix
        if not os.path.isfile(outfname):
            try:
                open(outfname, 'w')
                os.unlink(outfname)
                return outfname
            except Exception:
                pass

        prefix += u'_'

        # Try foo_en__af_XXXXX.zip
        try:
            directory = os.path.split(os.path.abspath(infilename))[0]
            if not directory:
                directory = None
            fd, outfname = mkstemp(suffix=suffix, prefix=prefix, dir=directory)
            os.close(fd)
            if os.path.isfile(outfname):
                os.unlink(outfname)
            return outfname
        except Exception:
            pass

        # Try /tmp/foo_en__af_XXXXX.zip as a last resort
        fd, outfname = mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        if os.path.isfile(outfname):
            os.unlink(outfname)
        return outfname

    def _guess_export_filename(self, projfname):
        guess = projfname.split('/')[-1]
        bundle_fname = self.get_bundle_filename()
        if bundle_fname:
            directory = os.path.split(os.path.abspath(bundle_fname))[0]
            guess = os.path.join(directory, guess)
        if os.path.isfile(guess):
            directory, fname = os.path.split(guess)
            basefname, extensions = proj.split_extensions(fname)
            guess = basefname + u'_%s__%s' % (
                self.main_controller.lang_controller.source_lang.code,
                self.main_controller.lang_controller.target_lang.code
            )
            guess += os.extsep + extensions
            guess = os.path.join(directory, guess)
        return guess


    # EVENT HANDLERS #
    def _on_controller_registered(self, main_controller, controller):
        if controller is main_controller.lang_controller:
            main_controller.disconnect(self._controller_register_id)
            main_controller.lang_controller.connect('source-lang-changed', self._on_source_lang_changed)
            main_controller.lang_controller.connect('target-lang-changed', self._on_target_lang_changed)

    def _on_source_lang_changed(self, _sender, langcode):
        self.store.set_source_language(langcode)

    def _on_target_lang_changed(self, _sender, langcode):
        self.store.set_target_language(langcode)

    def _unit_modified(self, emitter, unit):
        self._modified = True
        self.main_controller.set_saveable(self._modified)
