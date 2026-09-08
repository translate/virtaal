#
# Copyright 2008-2009 Zuza Software Foundation
# Copyright 2013 F Wolff
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

"""Contains the AutoCorrector class."""

import os
import re

from gi.repository import GLib

from virtaal.controllers.baseplugin import BasePlugin
from virtaal.views.widgets.textbox import TextBox


class AutoCorrector:
    """
    Does auto-correction on editable text widgets using OpenOffice.org auto-
    correction files.
    """

    wordsep_re = re.compile(r'\W+', re.UNICODE)

    REPLACEMENT, REGEX = range(2)

    def __init__(self, main_controller, lang='', acorpath=None):
        """Create a new AutoCorrector instance and load the LibreOffice
            auto-correction data for language code 'lang'.

            @type  lang: str
            @param lang: The code of the language to load auto-correction data
                for. See M{load_dictionary} for more information about how this
                parameter is used.
            @type  acorpath: str
            @param acorpath: The path to the directory holding one
                subdirectory per locale, each with a DocumentList.xml
                (see autocorrect_source.py) - <acorpath>/<lang>/DocumentList.xml.
            """
        self.main_controller = main_controller
        self.lang = None
        if acorpath is None or not os.path.isdir(acorpath):
            acorpath = os.path.curdir
        self.acorpath = acorpath
        self.load_dictionary(lang)
        self.widgets = set()

    def add_widget(self, widget):
        """Add a widget (currently only C{TextBox}s are accepted) to the
            list of widgets to do auto-correction for.
            """
        if not self.correctiondict:
            return # No dictionary to work with, so we can't handle any widgets

        if widget in self.widgets:
            return # Widget already added

        if isinstance(widget, TextBox):
            self._add_textbox(widget)
            return

        raise ValueError("Widget type %s not supported." % (type(widget)))

    def autocorrect(self, src, endindex, inserted=''):
        """Apply auto-correction to source string.

            @type  src: str
            @param src: The candidate-string for auto-correction.
            @type  endindex: int
            @param endindex: The logical end of the string. ie. The part of the
                string _before_ this index tested for the presence of a
                correctable string.
            @type  inserted: str
            @param inserted: The string that was inserted at I{endindex}

            @rtype: 2-tuple
            @return: The range in C{src} to be changed (or C{None} if no
                correction was found) as well as the string to replace that
                range with.
            """
        if not self.correctiondict:
            return None, ''

        candidate = src[:endindex]

        for key in self.correctiondict:
            mobj = self.correctiondict[key][self.REGEX].search(candidate)
            if mobj:
                replace_range = mobj.start(), mobj.end()
                replacement = self.correctiondict[key][self.REPLACEMENT]
                return replace_range, replacement

        return None, '' # No corrections done

    def clear_widgets(self):
        """Removes references to all widgets that is being auto-corrected."""
        for w in set(self.widgets):
            self.remove_widget(w)

    def load_dictionary(self, lang, force=False):
        """Load the LibreOffice auto-correction data for language 'lang'.

            Data lives one directory per locale under self.acorpath
            (see autocorrect_source.py), each holding a bare
            DocumentList.xml - <acorpath>/<lang>/DocumentList.xml. This
            handles "af", "af_ZA" or "af-ZA": tries the exact locale
            directory first ("af_ZA"), then the first directory found
            starting with the bare language part ("af").

            force re-loads even if 'lang' is already self.lang - used
            after a background download completes for a language that
            had nothing available the first time round.
            """
        if lang == self.lang and not force:
            return

        if not lang:
            self.correctiondict = {}
            self.lang = ''
            return

        lang = lang.replace('-', '_')
        xml_bytes = self._read_document_list(lang)
        if xml_bytes is None:
            self.correctiondict = {}
            self.lang = ''
            return

        from lxml import etree
        xml = etree.fromstring(xml_bytes)
        # Sample element from DocumentList.xml (it has no root element!):
        #   <block-list:block block-list:abbreviated-name="teh" block-list:name="the"/>  # codespell:ignore teh
        # This means that xml.iterchildren() will return an iterator over all
        # of <block-list> elements and entry.values() will return a 2-tuple
        # with the values of the "abbreviated-name" and "name" attributes.
        # That is how I got to the simple line below.
        self.correctiondict = dict([entry.values() for entry in xml.iterchildren()])

        # Add auto-correction regex for each loaded word.
        for key, value in self.correctiondict.items():
            # lxml gives bytestrings for ASCII only values
            self.correctiondict[key] = (str(value), re.compile(r'\b%s$' % (re.escape(key)), re.UNICODE))

        self.lang = lang
        return

    def _read_document_list(self, lang):
        """The raw DocumentList.xml bytes for lang, or None if nothing
            local covers it."""
        exact = os.path.join(self.acorpath, lang, 'DocumentList.xml')
        if os.path.isfile(exact):
            with open(exact, 'rb') as f:
                return f.read()

        if not os.path.isdir(self.acorpath):
            return None
        langpart = lang.split('_')[0]
        for name in sorted(os.listdir(self.acorpath)):
            if name == langpart or name.startswith(langpart + '_'):
                candidate = os.path.join(self.acorpath, name, 'DocumentList.xml')
                if os.path.isfile(candidate):
                    with open(candidate, 'rb') as f:
                        return f.read()
        return None

    def remove_widget(self, widget):
        """Remove a widget (currently only C{TextBox}es are accepted) from
            the list of widgets to do auto-correction for.
            """
        if not self.correctiondict:
            return

        if isinstance(widget, TextBox) and widget in self.widgets:
            self._remove_textbox(widget)

    def set_widgets(self, widget_collection):
        """Replace the widgets being auto-corrected with the collection given."""
        self.clear_widgets()
        for w in widget_collection:
            self.add_widget(w)

    def _add_textbox(self, textbox):
        """Add the given C{TextBox} to the list of widgets to do auto-
            correction on.
            """
        if not hasattr(self, '_textbox_handler_ids'):
            self._textbox_handler_ids = {}

        handler_id = textbox.connect(
            'text-inserted',
            self._on_insert_text
        )
        self._textbox_handler_ids[textbox] = handler_id
        self.widgets.add(textbox)

    def _on_insert_text(self, textbox, text, cursorpos, elem):
        if not isinstance(text, str):
            return
        if not self.wordsep_re.split(text)[-1]:
            bufftext = str(elem)
            offset = elem.gui_info.gui_to_tree_index(cursorpos)
            reprange, replacement = self.autocorrect(bufftext, offset, text)
            if reprange is not None:
                # Updating of the buffer is deferred until after this signal
                # and its side effects are taken care of. We abuse
                # GLib.idle_add for that.
                def correct_text():
                    buffer = textbox.buffer
                    start_iter = elem.gui_info.treeindex_to_iter(reprange[0])
                    end_iter = elem.gui_info.treeindex_to_iter(reprange[1], (reprange[0], start_iter))

                    self.main_controller.undo_controller.record_start()
                    buffer.delete(start_iter, end_iter)
                    buffer.insert(end_iter, replacement)
                    self.main_controller.undo_controller.record_stop()

                    newcursorpos = elem.gui_info.tree_to_gui_index(reprange[0]) + len(replacement) + len(text)
                    def refresh():
                        textbox.refresh_cursor_pos = newcursorpos
                        textbox.refresh()

                    GLib.idle_add(refresh)
                    return False

                GLib.idle_add(correct_text)

    def _remove_textbox(self, textbox):
        """Remove the given C{TextBox} from the list of widgets to do
            auto-correction on.
            """
        if not hasattr(self, '_textbox_handler_ids'):
            return
        # Disconnect the "insert-text" event handler
        textbox.disconnect(self._textbox_handler_ids[textbox])
        self.widgets.remove(textbox)


class Plugin(BasePlugin):
    description = _('Automatically correct text while you type')
    display_name = _('AutoCorrector')
    version = 0.1

    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name
        self.main_controller = main_controller

        self._init_plugin()

    def _init_plugin(self):
        from virtaal.support.autocorrect_source import autocorrect_root_dir
        self.autocorr = AutoCorrector(self.main_controller, acorpath=autocorrect_root_dir())
        self._autocorr_tried = set()

        def on_cursor_change(cursor):
            def add_widgets():
                self.autocorr.clear_widgets()
                for target in self.main_controller.unit_controller.view.targets:
                    self.autocorr.add_widget(target)
                return False

            GLib.idle_add(add_widgets)

        def maybe_download(lang):
            # Nothing local covered it (load_dictionary() always
            # replaces correctiondict, so this reflects lang's own
            # outcome) - try once per language per run.
            if not lang or self.autocorr.correctiondict or lang in self._autocorr_tried:
                return
            self._autocorr_tried.add(lang)

            def on_done():
                self.autocorr.load_dictionary(lang, force=True)
                on_cursor_change(None)

            from virtaal.support.autocorrect_downloader import AutocorrectDownloader
            AutocorrectDownloader(lang, on_done=on_done).start()

        def on_store_loaded(storecontroller):
            lang = self.main_controller.lang_controller.target_lang.code
            self.autocorr.load_dictionary(lang=lang)
            maybe_download(lang)

            if getattr(self, '_cursor_changed_id', None):
                self.store_cursor.disconnect(self._cursor_changed_id)
            self.store_cursor = storecontroller.cursor
            self._cursor_changed_id = self.store_cursor.connect('cursor-changed', on_cursor_change)
            on_cursor_change(self.store_cursor)

        def on_target_lang_changed(lang_controller, lang):
            self.autocorr.load_dictionary(lang)
            maybe_download(lang)
            # If the previous language didn't have a correction list, we might
            # have never attached, so let's make sure we attach.
            on_cursor_change(None)


        self._store_loaded_id = self.main_controller.store_controller.connect('store-loaded', on_store_loaded)

        if self.main_controller.store_controller.get_store():
            # Connect to already loaded store. This happens when the plug-in is enabled after loading a store.
            on_store_loaded(self.main_controller.store_controller)

        self._target_lang_changed_id = self.main_controller.lang_controller.connect('target-lang-changed', on_target_lang_changed)

    def destroy(self):
        """Remove all signal-connections."""
        self.autocorr.clear_widgets()
        self.main_controller.store_controller.disconnect(self._store_loaded_id)
        if getattr(self, '_cursor_changed_id', None):
            self.store_cursor.disconnect(self._cursor_changed_id)
