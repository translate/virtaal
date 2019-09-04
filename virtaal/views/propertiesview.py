#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Zuza Software Foundation
# Copyright 2016 F Wolff
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

from gi.repository import Gtk

from baseview import BaseView
from virtaal.common import GObjectWrapper


def _statistics(stats):
    """return string tuples (Description, value) when given the output of
    statsdb.StatsCache::file_extended_totals"""
    descriptions = {
            "empty": _("Untranslated:"),
            "needs-work": _("Needs work:"),
            "rejected": _("Rejected:"),
            "needs-review": _("Needs review:"),
            "unreviewed": _("Translated:"),
            "final": _("Reviewed:"),
    }
    from translate.storage import statsdb
    state_dict = statsdb.extended_state_strings

    # just to check that the code didn't get out of sync somewhere:
    if not set(descriptions.iterkeys()) == set(state_dict.itervalues()):
        logging.warning("statsdb.state_dict doesn't correspond to descriptions here")

    statistics = []
    # We want to build them up from untranslated -> reviewed
    for state in sorted(state_dict.iterkeys()):
        key = state_dict[state]
        if not key in stats:
            continue
        statistics.append((descriptions[key], stats[key]['units'], stats[key]['sourcewords']))
    return statistics


def _nice_percentage(numerator, denominator):
    """Returns a string that is a nicely readable percentage."""
    if numerator == 0:
        return _("(0%)")
    if numerator == denominator:
        return _("(100%)")
    percentage = numerator * 100.0 / denominator
    #l10n: This is the formatting for percentages in the file properties. If unsure, just copy the original.
    return _("(%04.1f%%)") % percentage


class PropertiesView(BaseView, GObjectWrapper):
    """Load, display and control the "Properties" dialog."""

    __gtype_name__ = 'PropertiesView'

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)
        self.controller = controller
        self._widgets = {}
        self.data = {}
        self._setup_key_bindings()
        self._setup_menu_item()

    def _get_widgets(self):
        self.gui = self.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='PropertiesDlg',
            domain="virtaal"
        )

        widget_names = (
            'tbl_properties',
            'lbl_type', 'lbl_location', 'lbl_filesize',
            'lbl_word_total', 'lbl_string_total',
            'vbox_word_labels', 'vbox_word_stats', 'vbox_word_perc',
            'vbox_string_labels', 'vbox_string_stats', 'vbox_string_perc',
        )
        for name in widget_names:
            self._widgets[name] = self.gui.get_object(name)

        self._widgets['dialog'] = self.gui.get_object('PropertiesDlg')
        self._widgets['dialog'].set_transient_for(self.controller.main_controller.view.main_window)
        self._widgets['dialog'].set_icon(self.controller.main_controller.view.main_window.get_icon())

    def _init_gui(self):
        self._get_widgets()

    def _setup_key_bindings(self):
        from gi.repository import Gdk
        Gtk.AccelMap.add_entry("<Virtaal>/File/Properties", Gdk.KEY_Return, Gdk.ModifierType.MOD1_MASK)

    def _setup_menu_item(self):
        mainview = self.controller.main_controller.view
        menu_file = mainview.gui.get_object('menu_file')
        mnu_properties = mainview.gui.get_object('mnu_properties')

        accel_group = menu_file.get_accel_group()
        if not accel_group:
            accel_group = Gtk.AccelGroup()
            menu_file.set_accel_group(accel_group)
            mainview.add_accel_group(accel_group)

        mnu_properties.set_accel_path("<Virtaal>/File/Properties")
        mnu_properties.connect('activate', self._show_properties)

    # ACCESSORS #


    # METHODS #
    def show(self):
        if not self._widgets:
            self._init_gui()
        self.controller.update_gui_data()
        statistics = _statistics(self.stats)
        tbl_properties = self._widgets['tbl_properties']
        if self.controller.main_controller.store_controller.is_modified():
            tbl_properties.set_tooltip_text(_("Save the file for up-to-date information"))
        else:
            tbl_properties.set_tooltip_text("")
        vbox_word_labels = self._widgets['vbox_word_labels']
        vbox_word_stats = self._widgets['vbox_word_stats']
        vbox_word_perc = self._widgets['vbox_word_perc']
        vbox_string_labels = self._widgets['vbox_string_labels']
        vbox_string_stats = self._widgets['vbox_string_stats']
        vbox_string_perc = self._widgets['vbox_string_perc']
        # Remove all previous work so that we can start afresh:
        for vbox in (vbox_word_labels, vbox_word_stats, vbox_word_perc,
                vbox_string_labels, vbox_string_stats, vbox_string_perc):
            for child in vbox.get_children():
                vbox.remove(child)
        total_words = 0
        total_strings = 0
        for (description, strings, words) in statistics:
            # Add two identical labels for the word/string descriptions
            lbl_desc = Gtk.Label(label=description)
            lbl_desc.set_alignment(1.0, 0.5) # Right aligned
            lbl_desc.show()
            vbox_word_labels.pack_start(lbl_desc, True, True, 0)

            lbl_desc = Gtk.Label(label=description)
            lbl_desc.set_alignment(1.0, 0.5) # Right aligned
            lbl_desc.show()
            vbox_string_labels.pack_start(lbl_desc, True, True, 0)

            # Now for the numbers
            total_words += words
            lbl_stats = Gtk.Label(label=str(words))
            lbl_stats.set_alignment(1.0, 0.5)
            lbl_stats.show()
            vbox_word_stats.pack_start(lbl_stats, True, True, 0)

            total_strings += strings
            lbl_stats = Gtk.Label(label=str(strings))
            lbl_stats.set_alignment(1.0, 0.5)
            lbl_stats.show()
            vbox_string_stats.pack_start(lbl_stats, True, True, 0)

        # Now we do the percentages:
        for (description, strings, words) in statistics:
            percentage = _nice_percentage(words, total_words)
            lbl_perc = Gtk.Label(label=percentage)
            lbl_perc.set_alignment(0.0, 0.5)
            lbl_perc.show()
            vbox_word_perc.pack_start(lbl_perc, True, True, 0)

            percentage = _nice_percentage(strings, total_strings)
            lbl_perc = Gtk.Label(label=percentage)
            lbl_perc.set_alignment(0.0, 0.5)
            lbl_perc.show()
            vbox_string_perc.pack_start(lbl_perc, True, True, 0)


        #l10n: The total number of words. You can not use %Id at this stage. If unsure, just copy the original.
        self._widgets['lbl_word_total'].set_markup(_("<b>%d</b>") % total_words)
        self._widgets['lbl_string_total'].set_markup(_("<b>%d</b>") % total_strings)

        self._widgets['lbl_type'].set_text(self.data['file_type'])
        filename = self.data.get('file_location', '')
        self._widgets['lbl_location'].set_text(filename)
        if filename:
            self._widgets['lbl_location'].set_tooltip_text(filename)
        file_size = self.data.get('file_size', 0)
        if file_size:
            #Let's get this from glib20.mo so that we're consistent with the file dialogue
            from gettext import dgettext
            i18n_filesize = dgettext('glib20', u"%.1f KB") % (file_size / 1024.0)
            self._widgets['lbl_filesize'].set_text(i18n_filesize)

        self._widgets['dialog'].run()
        self._widgets['dialog'].hide()


    # EVENT HANDLERS #
    def _show_properties(self, *args):
        self.show()
