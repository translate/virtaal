#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


from gi.repository import GLib, Gtk
from translate.lang import data

from virtaal.models.langmodel import LanguageModel
from virtaal.views.baseview import BaseView


class LanguageAddDialog:
    """
    Represents and manages an instance of the dialog used for adding a language.
    """

    _editing = False

    # INITIALIZERS #
    def __init__(self, parent=None):
        super().__init__()

        self.gui = BaseView.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='LanguageAdder',
            domain='virtaal'
        )

        self._get_widgets()
        self._add_title = self.dialog.get_title()
        if isinstance(parent, Gtk.Widget):
            self.dialog.set_transient_for(parent)
            self.dialog.set_icon(parent.get_toplevel().get_icon())

        self.ent_langname.connect('changed', self._on_input_changed)
        self.ent_langcode.connect('changed', self._on_input_changed)
        self._update_ok_sensitivity()

    def _get_widgets(self):
        """Load the GtkBuilder file and get the widgets we would like to use."""
        widget_names = ('btn_add_ok', 'ent_langname', 'ent_langcode', 'sbtn_nplurals', 'ent_plural')

        for name in widget_names:
            setattr(self, name, self.gui.get_object(name))

        self.dialog = self.gui.get_object('LanguageAdder')


    # ACCESSORS #
    def _get_langname(self):
        return self.ent_langname.get_text()
    def _set_langname(self, value):
        self.ent_langname.set_text(value)
    langname = property(_get_langname, _set_langname)

    def _get_langcode(self):
        return self.ent_langcode.get_text()
    def _set_langcode(self, value):
        self.ent_langcode.set_text(value)
    langcode = property(_get_langcode, _set_langcode)

    def _get_nplurals(self):
        return int(self.sbtn_nplurals.get_value())
    def _set_nplurals(self, value):
        self.sbtn_nplurals.set_value(int(value))
    nplurals = property(_get_nplurals, _set_nplurals)

    def _get_plural(self):
        return self.ent_plural.get_text()
    def _set_plural(self, value):
        self.ent_plural.set_text(value)
    plural = property(_get_plural, _set_plural)


    # METHODS #
    def clear(self):
        for entry in (self.ent_langname, self.ent_langcode, self.ent_plural):
            entry.set_text('')
        self.sbtn_nplurals.set_value(2)

    def run(self, clear=True):
        if clear:
            self.clear()
        self._update_ok_sensitivity()
        self.dialog.show()
        self.dialog.present()
        transient_for = self.dialog.get_transient_for()
        response = self.dialog.run() == Gtk.ResponseType.OK
        self.dialog.hide()
        if transient_for is not None:
            GLib.idle_add(transient_for.present)
        return response

    def run_edit(self, name, code, nplurals, plural):
        """Edit a known language's plural information; its name and code
            stay as they are."""
        self._editing = True
        self.clear()
        self.langname, self.langcode, self.nplurals, self.plural = name, code, nplurals, plural
        self.dialog.set_title(_('Edit Language'))
        for entry in (self.ent_langname, self.ent_langcode):
            entry.set_sensitive(False)
        try:
            return self.run(clear=False)
        finally:
            self._editing = False
            self.dialog.set_title(self._add_title)
            for entry in (self.ent_langname, self.ent_langcode):
                entry.set_sensitive(True)

    def check_input_sanity(self):
        if self._editing:
            return ''

        if not self.langname.strip():
            return _('Enter a language name.')

        code = self.langcode
        if not code.isascii():
            return _('Language code must be an ASCII string.')

        if len(code) < 2:
            return _('Language code must be at least 2 characters long.')

        if any(c.isspace() for c in code):
            return _('Language code must not contain spaces.')

        if data.normalize_code(code) in {data.normalize_code(c) for c in LanguageModel.languages}:
            return _('Language code %s is already used.') % code

        return ''


    # EVENT HANDLERS #
    def _on_input_changed(self, entry):
        self._update_ok_sensitivity()

    def _update_ok_sensitivity(self):
        err = self.check_input_sanity()
        self.btn_add_ok.set_sensitive(not err)
        self.btn_add_ok.set_tooltip_text(err or None)
