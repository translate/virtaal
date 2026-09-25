#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from gi.repository import GObject

from virtaal.common import GObjectWrapper

from .basecontroller import BaseController


# TODO: Create an event that is emitted when a cursor is created
class StoreController(BaseController):
    """The controller for all store-level activities."""

    __gtype_name__ = 'StoreController'
    __gsignals__ = {
        'store-loaded': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'store-saved': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'store-closed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.store_controller = self
        self._unit_controller = None # This is set by UnitController itself when it is created

        self.cursor = None
        self.handler_ids = {}
        self._modified = False
        self.project = None
        self.store = None
        self._tempfiles = []
        self._view = None

        self._controller_register_id = self.main_controller.connect('controller-registered', self._on_controller_registered)

    def destroy(self):
        if self.project:
            del self.project
        for tempfile in self._tempfiles:
            try:
                os.unlink(tempfile)
            except Exception:
                pass


    # ACCESSORS #

    def _getview(self):
        if not self._view:
            from virtaal.views.storeview import StoreView
            self._view = StoreView(self)
        return self._view
    view = property(_getview)

    def get_nplurals(self, store=None):
        if not store:
            store = self.store
        return store and store.nplurals or 0

    def get_bundle_filename(self):
        """Returns the file name of the bundle archive, if we are working with one."""
        if self.project:
            from virtaal.support.bundleprojstore import BundleProjectStore
            if isinstance(self.project.store, BundleProjectStore):
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
            from virtaal.support.bundleprojstore import BundleProjectStore
            if isinstance(self.project.store, BundleProjectStore):
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

    def get_store_checks(self):
        store = self.get_store()
        if not store:
            raise ValueError('No store to get checker from')
        return store.checks

    def get_unit_celleditor(self, unit):
        """Load the given unit in via the C{UnitController} and return
            the C{Gtk.CellEditable} it creates."""
        return self.unit_controller.load_unit(unit)

    def is_modified(self):
        return self._modified

    def set_modified(self, value):
        """Set the modified flag, also updating set_saveable()."""
        self._modified = value
        self.main_controller.set_saveable(value)

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
        if self.cursor.deref() is unit:
            # Unit is already selected; no need to do more work
            return

        i = 0
        try:
            # list.index() here is O(n) (and unit.__eq__ isn't cheap), but
            # select_unit() is only reached from search-result jumps and
            # undo/redo, not per-navigation, so it's a deliberate tradeoff
            # rather than a hot-path problem worth an index-based API.
            i = self.store.get_units().index(unit)
        except Exception as exc:
            import logging
            logging.debug('Unit not found:\n%s' % (exc))

        if force:
            self.cursor.force_index(i)
        else:
            self.cursor.index = i

    def _open_bundle(self, filename):
        import logging

        from virtaal.models.storemodel import StoreModel
        from virtaal.support import bundleprojstore
        try:
            from virtaal.support.project import Project
            self.project = Project(bundleprojstore.BundleProjectStore(filename))
        except bundleprojstore.InvalidBundleError as err:
            logging.exception('Unable to load project bundle')

        if not len(self.project.store.transfiles):
            # FIXME: Ask the user to select a source file to convert?
            if not len(self.project.store.sourcefiles):
                raise bundleprojstore.InvalidBundleError(_('No source or translatable files in bundle'))
            self.project.convert_forward(self.project.store.sourcefiles[0])

        # FIXME: Ask the user which translatable file to open?
        transfile = self.project.get_file(self.project.store.transfiles[0])
        self.real_filename = transfile.name
        logging.info(
            'Editing translation file %s:%s' %
            (filename, self.project.store.transfiles[0])
        )
        self.store = StoreModel(transfile, self)

    def _open_plain(self, filename):
        from virtaal.models.storemodel import StoreModel
        self.store = StoreModel(filename, self)

    def _rename_pot_template(self, filename, force_saveas):
        import re
        pot_re = re.compile(r"\.pot(\.gz|\.bz2)?$")
        if pot_re.search(filename):
            force_saveas = True
            filename = pot_re.sub('.po', filename)
            self.store._trans_store.filename = filename
        return filename, force_saveas

    def open_file(self, filename, uri='', forget_dir=False):
        extension = filename.split(os.extsep)[-1]
        force_saveas = False
        if extension == 'zip':
            self._open_bundle(filename)
        else:
            self._open_plain(filename)

        if len(self.store.get_units()) < 1:
            # clean up, otherwise self.store still contains the store
            self.close_file()
            raise ValueError(_('The file contains nothing to translate.'))

        self._modified = False

        # if file is a template, force saveas
        filename, force_saveas = self._rename_pot_template(filename, force_saveas)

        # forgetting the directory only makes sense if we force save as
        if force_saveas and forget_dir:
            filename = os.path.split(filename)[1]
            self.store._trans_store.filename = filename

        self.main_controller.set_force_saveas(force_saveas)
        self.main_controller.set_saveable(self._modified)

        from .cursor import Cursor
        self.cursor = Cursor(self.store, self.store.stats['total'])

        self.view.load_store(self.store)
        self.view.show()

        self.emit('store-loaded')

    def save_file(self, filename=None):
        self.unit_controller.prepare_for_save()
        if self.project is None:
            self.store.save_file(filename) # store.save_file() will raise an appropriate exception if necessary
        else:
            # XXX: filename is the name that the bundle archive should be saved
            #      as, seeing as self.store is opened from a temporary file
            #      (see virtaal.support.bundleprojstore.BundleProjectStore.get_file())
            self.store.save_file()

            proj_fname = self.project.get_proj_filename(self.real_filename)
            if not proj_fname:
                # This really shouldn't happen
                raise ValueError("Unable to determine file's project name: %s" % (self.real_filename))

            with open(self.real_filename, 'rb') as infile:
                self.project.update_file(proj_fname, infile)
            self.project.convert_forward(proj_fname, overwrite_output=True)
            self.project.save()
        self.set_modified(False)
        # Unlike open_file()/close_file(), a save doesn't clear the undo
        # stack, so it needs its own explicit clean-point mark.
        self.main_controller.undo_controller.model.mark_clean()
        self.emit('store-saved')

    def binary_export(self, filename):
        #TODO: confirm file extension is correct
        #TODO: confirm that there is something translated in the store
        from translate.tools.pocompile import POCompile
        compiler = POCompile()
        binary_output = open(filename, 'wb')
        binary_output.write(compiler.convertstore(self.store._trans_store))
        binary_output.close()

    def close_file(self):
        del self.project
        self.project = None
        self.store = None
        self.set_modified(False)
        self.view.hide() # This MUST be called BEFORE `self.cursor = None`
        self.emit('store-closed') # This should be emitted BEFORE `self.cursor = None` to allow any other modules to disconnect from the cursor
        self.cursor = None
        import gc
        gc.collect()

    def export_project_file(self, filename=None, openafter=False, readonly=False):
        if not self.project:
            return
        import logging
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
                from virtaal.support.project import split_extensions
                fname, ext = split_extensions(export_projfname.split('/')[-1])
                fname = 'virtaal_preview_' + fname + '_'
                ext = os.extsep + ext
                from tempfile import mkstemp
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

        # Let's entirely clear things in the view to ensure that no signals
        # are still attached to old models before we start changing things. See
        # bug 1854.
        self.view.load_store(None)
        self.store.update_file(filename)

        self._modified = True
        self.main_controller.set_saveable(self._modified)
        self.main_controller.set_force_saveas(self._modified)

        from .cursor import Cursor
        self.cursor = Cursor(self.store, self.store.stats['total'])

        self.view.load_store(self.store)
        self.view.show()

        self.emit('store-loaded')

    def update_store_checks(self, **kwargs):
        """Shortcut to C{StoreModel.update_stats()}"""
        store = self.get_store()
        if not store:
            raise ValueError('No store to get checker from')
        return store.update_checks(**kwargs)

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

    def _guess_export_filename(self, projfname):
        guess = projfname.split('/')[-1]
        bundle_fname = self.get_bundle_filename()
        if bundle_fname:
            directory = os.path.split(os.path.abspath(bundle_fname))[0]
            guess = os.path.join(directory, guess)
        if os.path.isfile(guess):
            directory, fname = os.path.split(guess)
            from virtaal.support.project import split_extensions
            basefname, extensions = split_extensions(fname)
            guess = basefname + '_%s__%s' % (
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
        # Guard against a late "modified" signal from a just-closed or
        # just-replaced file's teardown - both no file open at all, and
        # a unit belonging to a store that's since been replaced.
        if self.store is None:
            return
        if unit not in self.store.get_units():
            return
        self.set_modified(True)
