#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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
import gtk
import logging
from translate.lang.data import tr_lang

from virtaal.common import GObjectWrapper, pan_app

from baseview import BaseView
from widgets.popupbutton import PopupButton


class LanguageView(BaseView):
    """
    Manages the language selection on the GUI and communicates with its associated
    C{LanguageController}.
    """

    NUM_RECENT = 5
    """The number of recent language pairs to save/display."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self.recent_pairs = self._load_recent_pairs()
        self.gettext_lang = tr_lang(pan_app.settings.language["uilang"])
        self._init_gui()

    def _init_gui(self):
        self.menu = gtk.Menu()
        self.popupbutton = PopupButton()
        self.popupbutton.set_menu(self.menu)

        self.recent_items = []
        for i in range(self.NUM_RECENT):
            item = gtk.MenuItem('')
            item.connect('activate', self._on_pairitem_activated, i)
            self.recent_items.append(item)
        seperator = gtk.SeparatorMenuItem()
        self.other_item = gtk.MenuItem('Other...')
        self.other_item.connect('activate', self._on_other_activated)
        [self.menu.append(item) for item in (seperator, self.other_item)]
        self._update_recent_pairs()

    def _load_recent_pairs(self):
        # TODO: Implement this for real
        return [('ar', 'en'), ('en', 'af'), ('en', 'ar'), ('ar', 'en'), ('en_UK', 'af')]


    # METHODS #
    def set_language_pair(self, srclang, tgtlang):
        if srclang == 'en-US':
            srclang = 'en'

        pair = (srclang, tgtlang)
        if pair in self.recent_pairs:
            self.recent_pairs.remove(pair)

        self.recent_pairs.insert(0, pair)
        self.controller.source_lang = srclang
        self.controller.target_lang = tgtlang
        self._update_recent_pairs()
        self.popupbutton.text = self.recent_items[0].get_child().get_text()

    def show(self):
        """Add the managed C{PopupButton} to the C{MainView}'s status bar."""

        statusbar = self.controller.main_controller.view.status_bar

        for child in statusbar.get_children():
            if child is self.popupbutton:
                return
        statusbar.pack_start(self.popupbutton, expand=False)
        statusbar.show_all()

    def _update_recent_pairs(self):
        for i in range(self.NUM_RECENT):
            item = self.recent_items[i]
            if item.parent is self.menu:
                item.get_child().set_text('')
                self.menu.remove(item)

        i = 0
        for srclang, tgtlang in self.recent_pairs:
            srcinfo = self.controller.lookup_lang(srclang)
            tgtinfo = self.controller.lookup_lang(tgtlang)

            pairlabel = '%s -> %s' % (self.gettext_lang(srcinfo['name']), self.gettext_lang(tgtinfo['name']))
            self.recent_items[i].get_child().set_text(pairlabel)
            i += 1

        for i in range(self.NUM_RECENT):
            item = self.recent_items[i]
            if item.get_child().get_text():
                self.menu.insert(item, i)

        self.menu.show_all()


    # EVENT HANDLERS #
    def _on_other_activated(self, menuitem):
        pass

    def _on_pairitem_activated(self, menuitem, item_n):
        self.set_language_pair(*self.recent_pairs[item_n])
        logging.debug('Selected language pair: %s' % (self.recent_items[item_n].get_child().get_text()))
