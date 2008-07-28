#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
#
# This file is part of VirTaal.
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

"""Contains the AutoCompletor class."""

import gobject
import gtk
import re


class AutoCompletor(object):
    """
    Does auto-completion of registered words in registered widgets.
    """

    wordsep_re = re.compile(r'\W', re.UNICODE)

    DEFAULT_COMPLETION_LENGTH = 4 # The default minimum length of a word that may
                                  # be auto-completed.

    def __init__(self, word_list=[], comp_len=DEFAULT_COMPLETION_LENGTH):
        """Constructor.

            @type  word_list: iterable
            @param word_list: A list of words that should be auto-completed.
        """
        assert isinstance(word_list, list)
        self.comp_len = comp_len
        self._word_list = list(set(word_list))
        self.widgets = set()

    def add_widget(self, widget):
        """Add a widget to the list of widgets to do auto-completion for."""
        if widget in self.widgets:
            return # Widget already added

        if isinstance(widget, gtk.TextView):
            self._add_text_view(widget)
            return

        raise ValueError("Widget type %s not supported." % (type(widget)))

    def add_words(self, words):
        """Add a word or words to the list of words to auto-complete."""
        if isinstance(words, basestring):
            self._word_list.append(words)
        else:
            self._word_list += list(set(words))

    def autocomplete(self, word):
        for w in self._word_list:
            if w.startswith(word):
                return w, w[len(word):]
        return None, u''

    def clear_widgets(self):
        """Release all registered widgets from the spell of auto-completion."""
        for w in set(self.widgets):
            self.remove_widget(w)

    def clear_words(self):
        """Remove all registered words; effectively turns off auto-completion."""
        self.words.clear()

    def get_words_from_store(self, store):
        """Collect all words from the given translation store to use for
            auto-completion.

            The translation units obtained from C{store.getunits()} are assumed
            to have a C{gettarget()} method.

            @type  store: translate.storage.pypo.pofile
            @param store: The translation store to collect words from.
            """
        wordcounts = {}

        for unit in store.getunits():
            for word in self.wordsep_re.split( str(unit.gettarget()) ):
                if len(word) > self.comp_len:
                    try:
                        wordcounts[word] += 1
                    except KeyError:
                        wordcounts[word] = 1

        # Sort found words according to occurrances
        wordlist = []

        for word, count in wordcounts.items():
            if not wordlist:
                wordlist.append((word, count))
            elif count <= wordlist[-1][1]:
                wordlist.append((word, count))
            elif count >= wordlist[0][1]:
                wordlist[:0] = [(word, count)]

        wordlist = [items[0] for items in wordlist]
        self._word_list = list(set(wordlist))

    def remove_widget(self, widget):
        """Remove a widget (currently only C{gtk.TextView}s are accepted) from
            the list of widgets to do auto-correction for.
            """
        if isinstance(widget, gtk.TextView) and widget in self.widgets:
            self._remove_textview(widget)

    def remove_words(self, words):
        """Remove a word or words from the list of words to auto-complete."""
        if isinstance(words, basestring):
            self._word_list.remove(words)
        else:
            for w in words:
                try:
                    self._word_list.remove(w)
                except KeyError:
                    pass

    def _add_text_view(self, textview):
        """Add the given I{gtk.TextView} to the list of widgets to do auto-
            correction on.
            """
        if not hasattr(self, '_textbuffer_handler_ids'):
            self._textbuffer_handler_ids = {}

        if not hasattr(self, '_textview_handler_ids'):
            self._textview_handler_ids = {}

        handler_id = textview.get_buffer().connect(
            'insert-text',
            self._on_insert_text
        )
        self._textbuffer_handler_ids[textview] = handler_id

        handler_id = textview.connect(
            'key-press-event',
            self._on_textview_keypress
        )
        self._textview_handler_ids[textview] = handler_id

        self.widgets.add(textview)

    def _on_insert_text(self, buffer, iter, text, length):
        if self.wordsep_re.match(text):
            return
        prefix = unicode(buffer.get_text(buffer.get_start_iter(), iter) + text)
        postfix = unicode(buffer.get_text(iter, buffer.get_end_iter()))
        lastword = self.wordsep_re.split(prefix)[-1]

        if len(lastword) >= self.comp_len:
            completed_word, word_postfix = self.autocomplete(lastword)
            if completed_word == lastword:
                return

            if completed_word:
                completed_prefix = prefix[:-len(lastword)] + completed_word
                # Updating of the buffer is deferred until after this signal
                # and its side effects are taken care of. We abuse
                # gobject.idle_add for that.
                def complete_text():
                    buffer.props.text = u''.join([completed_prefix, postfix])
                    sel_iter_start = buffer.get_iter_at_offset(len(prefix))
                    sel_iter_end   = buffer.get_iter_at_offset(len(completed_prefix))
                    buffer.select_range(sel_iter_start, sel_iter_end)

                    # Combine the last two undo-actions into one
                    if hasattr(buffer, '__undo_stack'):
                        undostack = getattr(buffer, '__undo_stack')
                        undos = (undostack.pop(), undostack.pop())

                        def undo():
                            undos[0]() and undos[1]()
                            buffer.place_cursor(buffer.get_iter_at_offset(len(prefix)))
                            return True

                        undostack.push(undo)

                    return False
                gobject.idle_add(complete_text)

    def _on_textview_keypress(self, textview, event):
        """Catch tabs to the C{gtk.TextView} and make it keep the current selection."""
        iters = textview.get_buffer().get_selection_bounds()

        if event.keyval == gtk.keysyms.Tab and iters:
            textview.get_buffer().select_range(iters[1], iters[1])
            return True

    def _remove_textview(self, textview):
        """Remove the given C{gtk.TextView} from the list of widgets to do
            auto-correction on.
            """
        if not hasattr(self, '_textbuffer_handler_ids'):
            return
        # Disconnect the "insert-text" event handler
        textview.get_buffer().disconnect(self._textbuffer_handler_ids[textview])

        if not hasattr(self, '_textview_handler_ids'):
            return
        # Disconnect the "key-press-event" event handler
        textview.disconnect(self._textview_handler_ids[textview])

        self.widgets.remove(textview)
