#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging

from gi.repository import GLib, Gtk

from virtaal.common import GObjectWrapper
from virtaal.support.libi18n.numbers import format_number, format_percent

from .baseview import BaseView


def _statistics(stats, states=None):
    """return string tuples (Description, value) when given the output of
    statsdb.StatsCache::file_extended_totals

    states lists the state keys to include, counting absent ones as zero;
    defaults to the states in stats."""
    descriptions = {
            "empty": _("Untranslated:"),
            "needs-work": _("Needs work:"),
            "rejected": _("Rejected:"),
            "needs-review": _("Needs review:"),
            "unreviewed": _("Translated:"),
            "final": _("Reviewed:"),
    }
    from virtaal.support import statsdb
    state_dict = statsdb.extended_state_strings

    # just to check that the code didn't get out of sync somewhere:
    if not set(descriptions.keys()) == set(state_dict.values()):
        logging.warning("statsdb.state_dict doesn't correspond to descriptions here")

    if states is None:
        states = stats
    statistics = []
    # We want to build them up from untranslated -> reviewed
    for state in sorted(state_dict.keys()):
        key = state_dict[state]
        if not key in states:
            continue
        values = stats.get(key, {})
        statistics.append((descriptions[key], values.get('units', 0), values.get('sourcewords', 0)))
    return statistics


def _nice_percentage(numerator, denominator):
    """numerator as a percentage of denominator, in parentheses, with one
        decimal place unless it is 0% or 100%."""
    decimals = 0 if numerator in (0, denominator) else 1
    #l10n: A percentage in the file properties, e.g. "(25.5%)"
    return _("(%s)") % format_percent(numerator / denominator if denominator else 0, decimals)


class PropertiesView(BaseView, GObjectWrapper):
    """Load, display and control the "Properties" dialog."""

    __gtype_name__ = 'PropertiesView'

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)
        self.controller = controller
        self._widgets = {}
        self.data = {}
        self.stats = {}
        self.live_stats = None
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
            'lbl_saved_heading', 'lbl_live_heading',
            'lbl_word_live_total', 'lbl_string_live_total',
            'vbox_word_live_stats', 'vbox_string_live_stats',
        )
        for name in widget_names:
            self._widgets[name] = self.gui.get_object(name)

        self._widgets['dialog'] = self.gui.get_object('PropertiesDlg')
        self._widgets['dialog'].set_transient_for(self.controller.main_controller.view.main_window)
        self._widgets['dialog'].set_icon(self.controller.main_controller.view.main_window.get_icon())
        self._widgets['infobar'] = self._create_unsaved_infobar()

    def _create_unsaved_infobar(self):
        infobar = Gtk.InfoBar()
        infobar.set_message_type(Gtk.MessageType.WARNING)
        label = Gtk.Label(label=_("This file has unsaved changes."))
        label.show()
        infobar.get_content_area().pack_start(label, False, False, 0)
        infobar.add_button(_("_Save"), Gtk.ResponseType.ACCEPT)
        infobar.connect('response', self._on_infobar_response)
        content_area = self._widgets['dialog'].get_content_area()
        content_area.pack_start(infobar, False, False, 0)
        content_area.reorder_child(infobar, 0)
        return infobar

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
        self._refresh()

        # present() only raises/focuses an already-realized window -
        # show() explicitly first, run() alone doesn't guarantee that.
        self._widgets['dialog'].show()
        self._widgets['dialog'].present()
        transient_for = self._widgets['dialog'].get_transient_for()
        self._widgets['dialog'].run()
        self._widgets['dialog'].hide()
        if transient_for is not None:
            GLib.idle_add(transient_for.present)

    def _refresh(self):
        self.controller.update_gui_data()
        modified = self.live_stats is not None
        states = set(self.stats) | set(self.live_stats or {})
        self._clear_stat_rows()
        self._populate_stat_rows(_statistics(self.stats, states))
        if modified:
            self._populate_live_stat_rows(_statistics(self.live_stats, states), _statistics(self.stats, states))
        for name in ('infobar', 'lbl_saved_heading', 'lbl_live_heading',
                'lbl_word_live_total', 'lbl_string_live_total',
                'vbox_word_live_stats', 'vbox_string_live_stats'):
            self._widgets[name].set_visible(modified)
        self._update_file_info_labels()
        # Shrink back to fit once the unsaved-changes column is hidden.
        self._widgets['dialog'].resize(1, 1)

    def _clear_stat_rows(self):
        # Remove all previous work so that we can start afresh:
        for name in ('vbox_word_labels', 'vbox_word_stats', 'vbox_word_perc',
                'vbox_string_labels', 'vbox_string_stats', 'vbox_string_perc',
                'vbox_word_live_stats', 'vbox_string_live_stats'):
            vbox = self._widgets[name]
            for child in vbox.get_children():
                vbox.remove(child)

    def _populate_stat_rows(self, statistics):
        vbox_word_labels = self._widgets['vbox_word_labels']
        vbox_word_stats = self._widgets['vbox_word_stats']
        vbox_string_labels = self._widgets['vbox_string_labels']
        vbox_string_stats = self._widgets['vbox_string_stats']
        total_words = sum(words for (_desc, _strings, words) in statistics)
        total_strings = sum(strings for (_desc, strings, _words) in statistics)

        for (description, strings, words) in statistics:
            # Add two identical labels for the word/string descriptions
            lbl_desc = Gtk.Label(label=description)
            lbl_desc.set_xalign(1.0)  # Right aligned
            lbl_desc.show()
            vbox_word_labels.pack_start(lbl_desc, True, True, 0)

            lbl_desc = Gtk.Label(label=description)
            lbl_desc.set_xalign(1.0)  # Right aligned
            lbl_desc.show()
            vbox_string_labels.pack_start(lbl_desc, True, True, 0)

            # Number and percentage in one label, left aligned to match
            # lbl_word_total/lbl_string_total - keeping them as separate
            # labels/columns left the percentage's own alignment fighting
            # the number's, reading as neither left- nor right-aligned (#3683).
            word_percentage = _nice_percentage(words, total_words)
            lbl_stats = Gtk.Label(label='%s  %s' % (format_number(words), word_percentage))
            lbl_stats.set_xalign(0.0)
            lbl_stats.show()
            vbox_word_stats.pack_start(lbl_stats, True, True, 0)

            string_percentage = _nice_percentage(strings, total_strings)
            lbl_stats = Gtk.Label(label='%s  %s' % (format_number(strings), string_percentage))
            lbl_stats.set_xalign(0.0)
            lbl_stats.show()
            vbox_string_stats.pack_start(lbl_stats, True, True, 0)

        self._widgets['lbl_word_total'].set_markup('<b>%s</b>' % format_number(total_words))
        self._widgets['lbl_string_total'].set_markup('<b>%s</b>' % format_number(total_strings))

    def _populate_live_stat_rows(self, statistics, saved_statistics):
        """Fill the unsaved-changes column, in bold where it differs from the saved file."""
        total_words = sum(words for (_desc, _strings, words) in statistics)
        total_strings = sum(strings for (_desc, strings, _words) in statistics)

        for (_desc, strings, words), (_saved_desc, saved_strings, saved_words) in zip(statistics, saved_statistics):
            for vbox_name, value, saved_value, total in (
                    ('vbox_word_live_stats', words, saved_words, total_words),
                    ('vbox_string_live_stats', strings, saved_strings, total_strings)):
                text = GLib.markup_escape_text('%s  %s' % (format_number(value), _nice_percentage(value, total)))
                if value != saved_value:
                    text = '<b>%s</b>' % text
                lbl_stats = Gtk.Label()
                lbl_stats.set_markup(text)
                lbl_stats.set_xalign(0.0)
                lbl_stats.show()
                self._widgets[vbox_name].pack_start(lbl_stats, True, True, 0)

        self._widgets['lbl_word_live_total'].set_markup('<b>%s</b>' % format_number(total_words))
        self._widgets['lbl_string_live_total'].set_markup('<b>%s</b>' % format_number(total_strings))

    def _update_file_info_labels(self):
        self._widgets['lbl_type'].set_text(_(self.data['file_type']))
        filename = self.data.get('file_location', '')
        self._widgets['lbl_location'].set_text(filename)
        if filename:
            self._widgets['lbl_location'].set_tooltip_text(filename)
        file_size = self.data.get('file_size', 0)
        if file_size:
            self._widgets['lbl_filesize'].set_text(GLib.format_size(file_size))


    # EVENT HANDLERS #
    def _show_properties(self, *args):
        self.show()

    def _on_infobar_response(self, _infobar, response_id):
        if response_id == Gtk.ResponseType.ACCEPT and self.controller.save_file():
            self._refresh()
