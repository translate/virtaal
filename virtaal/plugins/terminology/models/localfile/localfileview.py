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

import gtk
import pango

from virtaal.views import BaseView


class LocalFileView:
    """
    Class that manages the localfile terminology plug-in's GUI presense and interaction.
    """

    # INITIALIZERS #
    def __init__(self, model):
        self.term_model = model
        self.controller = model.controller
        self.mainview = model.controller.main_controller.view
        self._signal_ids = []
        self._setup_menus()
        self.addterm = TermAddDialog(model=model)
        self.fileselect = FileSelectDialog(model=model)


    # METHODS #
    def _setup_menus(self):
        self.mnu_term = self.mainview.find_menu(_('_Terminology'))

        self.mnu_select_files, _menu = self.mainview.find_menu_item(_('Terminology _files...'), self.mnu_term)
        if not self.mnu_select_files:
            self.mnu_select_files = self.mainview.append_menu_item(_('Terminology _files...'), self.mnu_term)
        self._signal_ids.append((
            self.mnu_select_files,
            self.mnu_select_files.connect('activate', self._on_select_term_files)
        ))

        self.mnu_add_term, _menu = self.mainview.find_menu_item(_('Add _term...'), self.mnu_term)
        if not self.mnu_add_term:
            self.mnu_add_term = self.mainview.append_menu_item(_('Add _term...'), self.mnu_term)
        self._signal_ids.append((
            self.mnu_add_term,
            self.mnu_add_term.connect('activate', self._on_add_term)
        ))

    def destroy(self):
        for gobj, signal_id in self._signal_ids:
            gobj.disconnect(signal_id)

        menuitem, menu = self.mainview.find_menu_item(_('Terminology _files...'), self.mnu_term)
        if menuitem and menu:
            assert menu is self.mnu_term
            assert menuitem is self.mnu_select_files
            menu.get_submenu().remove(menuitem)


    # EVENT HANDLERS #
    def _on_add_term(self, menuitem):
        self.addterm.run(parent=self.mainview.main_window)

    def _on_select_term_files(self, menuitem):
        self.fileselect.run(parent=self.mainview.main_window)


class FileSelectDialog:
    """
    Wrapper for the selection dialog, created in Glade, to manage the list of
    files used by this plug-in.
    """

    COL_FILE, COL_EXTEND = range(2)

    # INITIALIZERS #
    def __init__(self, model):
        self.controller = model.controller
        self.term_model = model
        self.gladefilename, self.gui = BaseView.load_glade_file(
            ["virtaal", "virtaal.glade"],
            root='TermFilesDlg',
            domain='virtaal'
        )
        self._get_widgets()
        self._init_treeview()

    def _get_widgets(self):
        widget_names = ('btn_add_file', 'btn_remove_file', 'tvw_termfiles')

        for name in widget_names:
            setattr(self, name, self.gui.get_widget(name))

        self.dialog = self.gui.get_widget('TermFilesDlg')
        self.btn_add_file.connect('clicked', self._on_add_file_clicked)
        self.btn_remove_file.connect('clicked', self._on_remove_file_clicked)

    def _init_treeview(self):
        self.lst_files = gtk.ListStore(str, bool)
        self.tvw_termfiles.set_model(self.lst_files)

        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('File'))
        col.pack_start(cell)
        col.add_attribute(cell, 'text', self.COL_FILE)
        col.set_sort_column_id(0)
        self.tvw_termfiles.append_column(col)

        cell = gtk.CellRendererToggle()
        cell.set_radio(True)
        cell.connect('toggled', self._on_toggle)
        col = gtk.TreeViewColumn(_('Extendible'))
        col.pack_start(cell)
        col.add_attribute(cell, 'active', self.COL_EXTEND)
        self.tvw_termfiles.append_column(col)

        extend_file = self.term_model.config.get('extendfile', '')
        files = self.term_model.config['files']
        for f in files:
            self.lst_files.append([f, f == extend_file])

        # If there was no extend file, select the first one
        for row in self.lst_files:
            if row[self.COL_EXTEND]:
                break
        else:
            itr = self.lst_files.get_iter_first()
            if itr and self.lst_files.iter_is_valid(itr):
                self.lst_files.set_value(itr, self.COL_EXTEND, True)
                self.term_model.config['extendfile'] = self.lst_files.get_value(itr, self.COL_FILE)
                self.term_model.save_config()


    # METHODS #
    def run(self, parent=None):
        if isinstance(parent, gtk.Widget):
            self.dialog.set_transient_for(parent)

        self.dialog.show_all()
        self.dialog.run()
        self.dialog.hide()


    # EVENT HANDLERS #
    def _on_add_file_clicked(self, button):
        dlg = gtk.FileChooserDialog(
            _('Select file(s) to add...'),
            self.controller.main_controller.view.main_window,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)
        )
        dlg.set_select_multiple(True)
        dlg.show_all()
        response = dlg.run()
        dlg.hide()

        if response != gtk.RESPONSE_OK:
            return

        mainview = self.term_model.controller.main_controller.view
        currfiles = [row[self.COL_FILE] for row in self.lst_files]
        from translate.storage import factory
        for filename in dlg.get_filenames():
            if filename in currfiles:
                continue
            # Try and open filename as a translation store
            try:
                store = factory.getobject(filename)
                currfiles.append(filename)
                self.lst_files.append([filename, False])
            except Exception, exc:
                message = _('Unable to load %(filename)s:\n\n%(errormsg)s') % {'filename': filename, 'errormsg': str(exc)}
                mainview.show_error_dialog(title=_('Error opening file'), message=message)

        self.term_model.config['files'] = currfiles
        self.term_model.save_config()

    def _on_remove_file_clicked(self, button):
        model, selected = self.tvw_termfiles.get_selection().get_selected()
        if not selected:
            return

        remfile = model.get_value(selected, self.COL_FILE)
        extend = model.get_value(selected, self.COL_EXTEND)
        self.term_model.config['files'].remove(remfile)

        if extend:
            self.term_model.config['extendfile'] = ''
            itr = model.get_iter_first()
            if itr and model.iter_is_valid(itr):
                model.set_value(itr, self.COL_EXTEND, True)
                self.term_model.config['extendfile'] = model.get_value(itr, self.COL_FILE)

        self.term_model.save_config()
        model.remove(selected)

    def _on_toggle(self, renderer, path):
        toggled_file = self.lst_files.get_value(self.lst_files.get_iter(path), self.COL_FILE)

        itr = self.lst_files.get_iter_first()
        while itr is not None and self.lst_files.iter_is_valid(itr):
            self.lst_files.set_value(itr, self.COL_EXTEND, self.lst_files.get_value(itr, self.COL_FILE) == toggled_file)
            itr = self.lst_files.iter_next(itr)

        self.term_model.config['extendfile'] = toggled_file
        self.term_model.save_config()


class TermAddDialog:
    """
    Wrapper for the dialog used to add a new term to the terminology file.
    """

    # INITIALIZERS #
    def __init__(self, model):
        self.term_model = model
        self.lang_controller = model.controller.main_controller.lang_controller
        self.unit_controller = model.controller.main_controller.unit_controller

        self.gladefilename, self.gui = BaseView.load_glade_file(
            ["virtaal", "virtaal.glade"],
            root='TermAddDlg',
            domain='virtaal'
        )
        self._get_widgets()

    def _get_widgets(self):
        widget_names = ('ent_source', 'ent_target', 'lbl_srclang', 'lbl_tgtlang', 'lbl_filename', 'txt_comment')

        for name in widget_names:
            setattr(self, name, self.gui.get_widget(name))

        self.lbl_filename.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        self.dialog = self.gui.get_widget('TermAddDlg')


    # METHODS #
    def add_term_unit(self, source, target):
        # TODO: Find the correct way to add a new unit of the correct store's type to the terminology matcher.
        logging.debug('Adding new terminology term with source and target: [%s] | [%s]' % (source, target))

    def run(self, parent=None):
        if isinstance(parent, gtk.Widget):
            self.dialog.set_transient_for(parent)

        unitview = self.unit_controller.view

        source_text = u''
        for src in unitview.sources:
            selection = src.buffer.get_selection_bounds()
            if selection:
                source_text = src.get_text(*selection)
                break
        self.ent_source.set_text(source_text.strip())

        target_text = u''
        for tgt in unitview.targets:
            selection = tgt.buffer.get_selection_bounds()
            if selection:
                target_text = tgt.get_text(*selection)
                break
        self.ent_target.set_text(target_text.strip())

        self.lbl_srclang.set_text(_('Source lang — %(langname)s' % {'langname': self.lang_controller.source_lang.name}))
        self.lbl_tgtlang.set_text(_('Target lang — %(langname)s' % {'langname': self.lang_controller.target_lang.name}))
        self.lbl_filename.set_text(self.term_model.config.get('extendfile', ''))

        self.dialog.show_all()
        response = self.dialog.run()
        self.dialog.hide()

        if response != gtk.RESPONSE_OK:
            return

        self.add_term_unit(self.ent_source.get_text(), self.ent_target.get_text())
