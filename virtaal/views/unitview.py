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

import gtk
import logging
import re
from gobject import idle_add, GObject, SIGNAL_RUN_FIRST, TYPE_INT, TYPE_NONE, TYPE_PYOBJECT, TYPE_STRING
from translate.lang import factory

from virtaal.common import GObjectWrapper, pan_app

import markup
import rendering
from baseview import BaseView
from widgets.label_expander import LabelExpander


class UnitView(gtk.EventBox, GObjectWrapper, gtk.CellEditable, BaseView):
    """View for translation units and its actions."""

    __gtype_name__ = "UnitView"
    __gsignals__ = {
        'delete-text': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_STRING, TYPE_INT, TYPE_INT, TYPE_INT, TYPE_INT)),
        'insert-text': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_STRING, TYPE_STRING, TYPE_INT, TYPE_INT)),
        'modified': (SIGNAL_RUN_FIRST, TYPE_NONE, ()),
        'target-focused': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_INT,)),
    }

    # A regular expression to help us find a meaningful place to position the
    # cursor initially.
    first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

    # INITIALIZERS #
    def __init__(self, controller, unit):
        gtk.EventBox.__init__(self)
        GObjectWrapper.__init__(self)

        self.controller = controller
        self._focused_target_n = None
        self.gladefilename, self.gui = self.load_glade_file(["virtaal", "virtaal.glade"], root='UnitEditor', domain="virtaal")
        self.sources = []
        self.targets = []
        self.options = {}

        self.must_advance = False
        self._modified = False

        self.connect('key-press-event', self._on_key_press_event)

        self._get_widgets()
        self.load_unit(unit)


    # ACCESSORS #
    def is_modified(self):
        return self._modified

    def _get_focused_target_n(self):
        return self._focused_target_n
    def _set_focused_target_n(self, target_n):
        self.focus_text_view(self.targets[target_n])
    focused_target_n = property(_get_focused_target_n, _set_focused_target_n)

    def get_target_n(self, n):
        buff = self.targets[n].get_buffer()
        return buff.get_text(buff.get_start_iter(), buff.get_end_iter())

    def set_target_n(self, n, newtext, cursor_pos=-1):
        # TODO: Save cursor position and set after assignment
        buff = self.targets[n].get_buffer()
        buff.set_text(markup.escape(newtext))
        if cursor_pos > -1:
            buff.place_cursor(buff.get_iter_at_offset(cursor_pos))


    # METHODS #
    def copy_original(self, text_view):
        buf = text_view.get_buffer()
        position = buf.props.cursor_position
        old_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        lang = factory.getlanguage(self.controller.get_target_language())
        new_source = lang.punctranslate(self.unit.source)
        # if punctranslate actually changed something, let's insert that as an
        # undo step
        if new_source != self.unit.source:
            buf.set_text(markup.escape(self.unit.source))
            self.controller.main_controller.undo_controller.remove_blank_undo()
        buf.set_text(markup.escape(new_source))
        if old_text:
            self.controller.main_controller.undo_controller.remove_blank_undo()
        self.focus_text_view(text_view)
        return False

    def do_start_editing(self, *_args):
        """C{gtk.CellEditable.start_editing()}"""
        self.focus_text_view(self.targets[0])

    def focus_text_view(self, text_view):
        text_view.grab_focus()

        buf = text_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

        translation_start = self.first_word_re.match(text).span()[1]
        buf.place_cursor(buf.get_iter_at_offset(translation_start))

        self._focused_target_n = self.targets.index(text_view)
        self.emit('target-focused', self._focused_target_n)

    def load_unit(self, unit):
        """Load a GUI (C{gtk.CellEditable}) for the given unit."""
        if not unit:
            return None

        self.unit = unit
        self._get_widgets()
        self._build_default_editor()
        self.widgets['tbl_editor'].reparent(self)

        i = 0
        for target in self.targets:
            target._source_text = unit.source # FIXME: Find a better way to do this!
            buff = target.get_buffer()
            target.connect('key-press-event', self._on_text_view_key_press_event)
            buff.connect('changed', self._on_target_changed, i)
            buff.connect('insert-text', self._on_target_insert_text, i)
            buff.connect('delete-range', self._on_target_delete_range, i)
            i += 1

        for option in self.options.values():
            option.connect("toggled", self._on_fuzzy_toggled)

        self._modified = False

    def modified(self):
        self._modified = True
        self.emit('modified')

    def show(self):
        self.show()

    def _build_default_editor(self):
        """Build the default editor with the following components:
            - A C{gtk.TextView} for each source
            - A C{gtk.TextView} for each target
            - A C{gtk.ToggleButton} for the fuzzy option
            - A C{widgets.LabelExpander} for programmer notes
            - A C{widgets.LabelExpander} for translator notes
            - A C{widgets.LabelExpander} for context info"""
        self._layout_add_notes('programmer')
        self._layout_add_sources()
        self._layout_add_context_info()
        self._layout_add_targets()
        self._layout_add_notes('translator')
        self._layout_add_fuzzy()

    def _get_widgets(self):
        """Load the Glade file and get the widgets we would like to use."""
        self.widgets = {}

        widget_names = ('tbl_editor', 'vbox_middle', 'vbox_sources', 'vbox_targets', 'vbox_options')

        for name in widget_names:
            self.widgets[name] = self.gui.get_widget(name)


    # GUI BUILDING CODE #
    def _create_textbox(self, text='', editable=True, scroll_policy=gtk.POLICY_AUTOMATIC):
        textview = gtk.TextView()
        textview.set_editable(editable)
        textview.set_wrap_mode(gtk.WRAP_WORD)
        textview.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)
        textview.set_left_margin(2)
        textview.set_right_margin(2)
        textview.get_buffer().set_text(text)

        scrollwnd = gtk.ScrolledWindow()
        scrollwnd.set_policy(gtk.POLICY_NEVER, scroll_policy)
        scrollwnd.add(textview)

        return scrollwnd

    def _layout_add_notes(self, origin):
        textbox = self._create_textbox(
                self.unit.getnotes(origin),
                editable=False,
                scroll_policy=gtk.POLICY_NEVER
            )
        textview = textbox.get_child()
        labelexpander = LabelExpander(textbox, lambda *args: self.unit.getnotes(origin))

        self.widgets['vbox_middle'].add(labelexpander)
        if origin == 'programmer':
            self.widgets['vbox_middle'].reorder_child(labelexpander, 0)
        elif origin == 'translator':
            self.widgets['vbox_middle'].reorder_child(labelexpander, 4)

    def _layout_add_sources(self):
        num_sources = 1
        if self.unit.hasplural():
            num_sources = len(self.unit.source.strings)

        self.sources = []
        for i in range(num_sources):
            sourcestr = ''
            if self.unit.hasplural():
                sourcestr = self.unit.source.strings[i]
            elif i == 0:
                sourcestr = self.unit.source
            else:
                raise IndexError()

            source = self._create_textbox(
                    markup.escape(sourcestr),
                    editable=False,
                    scroll_policy=gtk.POLICY_NEVER
                )
            textview = source.get_child()
            textview.modify_font(rendering.get_source_font_description())
            # This causes some problems, so commented out for now
            #textview.get_pango_context().set_font_description(rendering.get_source_font_description())
            textview.get_pango_context().set_language(rendering.get_source_language())
            self.widgets['vbox_sources'].add(source)
            self.sources.append(textview)

    def _layout_add_context_info(self):
        textbox = self._create_textbox(
                self.unit.getcontext(),
                editable=False,
                scroll_policy=gtk.POLICY_NEVER
            )
        textview = textbox.get_child()
        labelexpander = LabelExpander(textbox, lambda *args: self.unit.getcontext())

        self.widgets['vbox_middle'].add(labelexpander)
        self.widgets['vbox_middle'].reorder_child(labelexpander, 2)

    def _layout_add_targets(self):
        num_targets = 1
        if self.unit.hasplural():
            num_targets = self.controller.nplurals

        # FIXME: Move add_spell_checking() and its call below to a more appropriate place.
        def add_spell_checking(text_view, language):
            try:
                import gtkspell
            except ImportError, e:
                gtkspell = None
            if gtkspell:
                try:
                    spell = gtkspell.Spell(text_view)
                    spell.set_language(language)
                except:
                    logging.info("Could not initialize spell checking")
                    gtkspell = None

        def on_text_view_n_press_event(text_view, event):
            """Handle special keypresses in the textarea."""
            # Automatically move to the next line if \n is entered

            if event.keyval == gtk.keysyms.n:
                buf = text_view.get_buffer()
                curpos = buf.props.cursor_position
                lastchar = buf.get_text(
                        buf.get_iter_at_offset(curpos-1),
                        buf.get_iter_at_offset(curpos)
                    )
                if lastchar == "\\":
                    buf.insert_at_cursor('n\n')
                    text_view.scroll_mark_onscreen(buf.get_insert())
                    return True
            return False

        def target_key_press_event(text_view, event, next_text_view):
            if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
                self.focus_text_view(next_text_view)
                return True
            return False

        def end_target_key_press_event(text_view, event, *_args):
            if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
                text_view.parent.parent.emit('key-press-event', event)
                return True
            return False

        self.targets = []
        for i in range(num_targets):
            if self.unit.hasplural() and self.controller.nplurals != len(self.unit.target.strings):
                targets = self.controller.nplurals * [u'']
                targets[:len(self.unit.target.strings)] = self.unit.target.strings
                self.unit.target = targets

            targetstr = ''
            if self.unit.hasplural():
                targetstr = self.unit.target.strings[i]
            elif i == 0:
                targetstr = self.unit.target
            else:
                raise IndexError()

            target = self._create_textbox(
                    markup.escape(targetstr),
                    editable=True,
                    scroll_policy=gtk.POLICY_AUTOMATIC
                )
            textview = target.get_child()
            textview.modify_font(rendering.get_target_font_description())
            textview.get_pango_context().set_font_description(rendering.get_target_font_description())
            textview.get_pango_context().set_language(rendering.get_target_language())
            textview.connect('key-press-event', on_text_view_n_press_event)

            add_spell_checking(textview, pan_app.settings.language['contentlang'])

            self.widgets['vbox_targets'].add(target)
            self.targets.append(textview)

        self.widgets['vbox_targets'].connect('key-press-event', self._on_key_press_event)

        for target, next_target in zip(self.targets, self.targets[1:]):
            target.connect('key-press-event', target_key_press_event, next_target)
        self.targets[-1].connect('key-press-event', end_target_key_press_event)

    def _layout_add_fuzzy(self):
        check_button = gtk.CheckButton(label=_('F_uzzy'))
        check_button.set_active(self.unit.isfuzzy())
        # FIXME: not allowing focus will probably raise various issues related to keyboard accesss.
        check_button.set_property("can-focus", False)

        self.options['fuzzy'] = check_button
        self.widgets['vbox_options'].add(check_button)


    # EVENT HANLDERS #
    def _on_fuzzy_toggled(self, toggle_button, *args):
        self.unit.markfuzzy(toggle_button.get_active())
        self.modified()

    def _on_key_press_event(self, _widget, event, *_args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            self.must_advance = True
            self.editing_done()
            return True
        return False

    def _on_target_changed(self, buffer, index):
        newtext = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
        if self.unit.hasplural():
            # FIXME: The following two lines are necessary because self.unit.target always
            # returns a new multistring, so you can't assign to an index directly.
            target = self.unit.target.strings
            target[index] = newtext
            self.unit.target = target
        elif index == 0:
            self.unit.target = newtext
        else:
            raise IndexError()

        self.modified()

    def _on_target_insert_text(self, buff, iter, ins_text, length, target_num):
        old_text = buff.get_text(buff.get_start_iter(), buff.get_end_iter())
        offset = len(buff.get_text(buff.get_start_iter(), iter)) # FIXME: Isn't there a better way to do this?

        self.emit('insert-text', old_text, ins_text, offset, target_num)

    def _on_target_delete_range(self, buff, start_iter, end_iter, target_num):
        cursor_iter = buff.get_iter_at_mark(buff.get_insert())
        cursor_pos = len(buff.get_text(buff.get_start_iter(), cursor_iter))
        old_text = buff.get_text(buff.get_start_iter(), buff.get_end_iter())
        start_offset = len(buff.get_text(buff.get_start_iter(), start_iter)) # FIXME: Isn't there a better way to do this?
        end_offset = len(buff.get_text(buff.get_start_iter(), end_iter)) # FIXME: Isn't there a better way to do this?

        self.emit('delete-text', old_text, start_offset, end_offset, cursor_pos, target_num)

    def _on_text_view_key_press_event(self, widget, event, *_args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            self.must_advance = True
            self.editing_done()
            return True

        # Alt-Down
        if event.keyval == gtk.keysyms.Down and event.state & gtk.gdk.MOD1_MASK:
            idle_add(self.copy_original, widget)
            return True
        return False
