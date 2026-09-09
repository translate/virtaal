#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


from gi.repository import Gtk

from virtaal.views.baseview import BaseView


class LanguageAddDialog:
    """
    Represents and manages an instance of the dialog used for adding a language.
    """

    # INITIALIZERS #
    def __init__(self, parent=None):
        super().__init__()

        self.gui = BaseView.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='LanguageAdder',
            domain='virtaal'
        )

        self._get_widgets()
        if isinstance(parent, Gtk.Widget):
            self.dialog.set_transient_for(parent)
            self.dialog.set_icon(parent.get_toplevel().get_icon())

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
        self.sbtn_nplurals.set_value(0)

    def run(self, clear=True):
        if clear:
            self.clear()
        response = self.dialog.run() == Gtk.ResponseType.OK
        self.dialog.hide()
        return response

    def check_input_sanity(self):
        # TODO: Add more sanity checks
        code = self.langcode
        try:
            ascii_code = str(code, 'ascii')
        except UnicodeDecodeError:
            return _('Language code must be an ASCII string.')

        if len(code) < 2:
            return _('Language code must be at least 2 characters long.')

        return ''
