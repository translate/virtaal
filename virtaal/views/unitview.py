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
from translate.lang import data
try:
    import gtkspell
except ImportError, e:
    gtkspell = None

from virtaal.common import GObjectWrapper, pan_app

import markup
import rendering
from baseview import BaseView
from widgets.label_expander import LabelExpander


class UnitView(gtk.EventBox, GObjectWrapper, gtk.CellEditable, BaseView):
    """View for translation units and its actions."""

    __gtype_name__ = "UnitView"
    __gsignals__ = {
        'delete-text':    (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_STRING, TYPE_INT, TYPE_INT, TYPE_INT, TYPE_INT)),
        'insert-text':    (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_STRING, TYPE_STRING, TYPE_INT, TYPE_INT)),
        'paste-start':    (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_STRING, TYPE_PYOBJECT, TYPE_INT)),
        'modified':       (SIGNAL_RUN_FIRST, TYPE_NONE, ()),
        'unit-done':      (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT,)),
        'target-focused': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_INT,)),
    }

    first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")
    """A regular expression to help us find a meaningful place to position the
        cursor initially."""

    MAX_SOURCES = 6
    """The number of text boxes to manage as sources."""
    MAX_TARGETS = 6
    """The number of text boxes to manage as targets."""

    # INITIALIZERS #
    def __init__(self, controller, unit=None):
        gtk.EventBox.__init__(self)
        GObjectWrapper.__init__(self)

        self.controller = controller
        self._focused_target_n = None
        self.gladefilename, self.gui = self.load_glade_file(["virtaal", "virtaal.glade"], root='UnitEditor', domain="virtaal")

        self.must_advance = False
        self._modified = False

        self.connect('key-press-event', self._on_key_press_event)

        self._widgets = {
            'context_info': None,
            'fuzzy': None,
            'notes': {},
            'sources': [],
            'targets': []
        }
        self._get_widgets()
        self._setup_menus()
        self.unit = None
        self.load_unit(unit)

    def _setup_menus(self):
        clipboard = gtk.Clipboard(selection=gtk.gdk.SELECTION_CLIPBOARD)
        def on_cut(menuitem):
            self.targets[self.focused_target_n].get_buffer().cut_clipboard(clipboard, True)
        def on_copy(menuitem):
            self.targets[self.focused_target_n].get_buffer().copy_clipboard(clipboard)
        def on_paste(menuitem):
            self.targets[self.focused_target_n].get_buffer().paste_clipboard(clipboard, None, True)

        maingui = self.controller.main_controller.view.gui
        maingui.get_widget('mnu_cut').connect('activate', on_cut)
        maingui.get_widget('mnu_copy').connect('activate', on_copy)
        maingui.get_widget('mnu_paste').connect('activate', on_paste)


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
        return data.forceunicode(markup.unescape(buff.get_text(buff.get_start_iter(), buff.get_end_iter())))

    def set_target_n(self, n, newtext, cursor_pos=-1, escape=True):
        # TODO: Save cursor position and set after assignment
        buff = self.targets[n].get_buffer()
        if escape:
            newtext = markup.escape(newtext)
        buff.set_text(newtext)
        if cursor_pos > -1:
            buff.place_cursor(buff.get_iter_at_offset(cursor_pos))

    sources = property(lambda self: self._widgets['sources'])
    targets = property(lambda self: self._widgets['targets'])


    # METHODS #
    def copy_original(self, text_view):
        buf = text_view.get_buffer()
        position = buf.props.cursor_position
        old_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        lang = factory.getlanguage(self.controller.main_controller.lang_controller.target_lang.code)
        new_source = lang.punctranslate(self.unit.source)
        # if punctranslate actually changed something, let's insert that as an
        # undo step
        if new_source != self.unit.source:
            buf.set_text(markup.escape(self.unit.source))
            self.controller.main_controller.undo_controller.remove_blank_undo()
        buf.set_text(markup.escape(new_source))
        if old_text:
            self.controller.main_controller.undo_controller.remove_blank_undo()

        # The following 2 lines were copied from focus_text_view() below
        translation_start = self.first_word_re.match(markup.escape(new_source)).span()[1]
        buf.place_cursor(buf.get_iter_at_offset(translation_start))

        return False

    def do_start_editing(self, *_args):
        """C{gtk.CellEditable.start_editing()}"""
        self.focus_text_view(self.targets[0])

    def do_editing_done(self, *_args):
        #logging.debug('emit("unit-done", self.unit=%s)' % (self.unit))
        #self.emit('unit-done', self.unit)
        pass

    def focus_text_view(self, text_view):
        text_view.grab_focus()

        buf = text_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

        translation_start = self.first_word_re.match(text).span()[1]
        buf.place_cursor(buf.get_iter_at_offset(translation_start))

        self._focused_target_n = self.targets.index(text_view)
        #logging.debug('emit("target-focused", focused_target_n=%d)' % (self._focused_target_n))
        self.emit('target-focused', self._focused_target_n)

    def load_unit(self, unit):
        """Load a GUI (C{gtk.CellEditable}) for the given unit."""
        if unit is self.unit and unit is not None:
            return
        self.unit = unit
        self.disable_signals(['modified', 'insert-text', 'delete-text'])
        self._update_editor_gui()
        self.enable_signals(['modified', 'insert-text', 'delete-text'])
        self._widgets['tbl_editor'].reparent(self)

        if unit is not None:
            for i in range(len(self.targets)):
                self.targets[i]._source_text = unit.source # FIXME: Find a better way to do this!

        self._modified = False

    def modified(self):
        self._modified = True
        #logging.debug('emit("modified")')
        self.emit('modified')

    def show(self):
        super(UnitView, self).show()

    def update_languages(self):
        srclang = self.controller.main_controller.lang_controller.source_lang.code
        tgtlang = self.controller.main_controller.lang_controller.target_lang.code

        for textview in self.sources:
            self._update_textview_language(textview, srclang)
            textview.modify_font(rendering.get_source_font_description())
            # This causes some problems, so commented out for now
            #textview.get_pango_context().set_font_description(rendering.get_source_font_description())
        for textview in self.targets:
            self._update_textview_language(textview, tgtlang)
            textview.modify_font(rendering.get_target_font_description())
            textview.get_pango_context().set_font_description(rendering.get_target_font_description())

    def _get_widgets(self):
        """Get the widgets we would like to use from the loaded Glade XML object."""
        if not getattr(self, '_widgets', None):
            self._widgets = {}

        widget_names = ('tbl_editor', 'vbox_middle', 'vbox_sources', 'vbox_targets', 'vbox_options', 'vbox_right')

        for name in widget_names:
            self._widgets[name] = self.gui.get_widget(name)

        self._widgets['vbox_targets'].connect('key-press-event', self._on_key_press_event)

    def _update_editor_gui(self):
        """Build the default editor with the following components:
            - A C{gtk.TextView} for each source
            - A C{gtk.TextView} for each target
            - A C{gtk.ToggleButton} for the fuzzy option
            - A C{widgets.LabelExpander} for programmer notes
            - A C{widgets.LabelExpander} for translator notes
            - A C{widgets.LabelExpander} for context info"""
        self._layout_update_notes('programmer')
        self._layout_update_sources()
        self._layout_update_context_info()
        self._layout_update_targets()
        self._layout_update_notes('translator')
        self._layout_update_fuzzy()

    def _update_textview_language(self, text_view, language):
        language = str(language)
        text_view.get_pango_context().set_language(rendering.get_language(language))

        global gtkspell
        if gtkspell is None:
            return

        try:
            import enchant
        except ImportError:
            return

        if not enchant.dict_exists(language):
            # Sometimes enchants *wants* a country code, other times it does not.
            # For the cases where it requires one, we look for the first language
            # code that enchant supports and use that one.
            if len(language) > 4:
                return

            for code in enchant.list_languages():
                if code.startswith(language):
                    language = code
                    break
            else:
                return

        if getattr(text_view, 'spell_lang', None) == language:
            return

        try:
            spell = None
            try:
                spell = gtkspell.get_from_text_view(text_view)
            except SystemError:
                pass
            if spell is None:
                spell = gtkspell.Spell(text_view)
            spell.set_language(language)
            spell.recheck_all()
            text_view.spell_lang = language
        except Exception:
            logging.exception("Could not initialize spell checking")
            gtkspell = None

    if not pan_app.DEBUG:
        try:
            import psyco
            psyco.cannotcompile(_update_textview_language)
        except ImportError, e:
            pass

    # GUI BUILDING CODE #
    def _create_sources(self):
        for i in range(len(self.sources), self.MAX_SOURCES):
            source = self._create_textbox('', editable=False, scroll_policy=gtk.POLICY_NEVER)
            textview = source.get_child()
            self._widgets['vbox_sources'].pack_start(source)
            self.sources.append(textview)

    def _create_targets(self):
        def on_text_view_n_press_event(text_view, event):
            """Handle special keypresses in the textarea."""
            # Alt-Down
            if event.keyval == gtk.keysyms.Down and event.state & gtk.gdk.MOD1_MASK:
                idle_add(self.copy_original, text_view)
                return True

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
                if next_text_view is not None and next_text_view.props.visible:
                    self.focus_text_view(next_text_view)
                else:
                    # text_view is the last text view in this unit, so we need to move on
                    # to the next one.
                    text_view.parent.parent.emit('key-press-event', event)
                return True
            return False

        for i in range(len(self.targets), self.MAX_TARGETS):
            target = self._create_textbox('', editable=True, scroll_policy=gtk.POLICY_AUTOMATIC)
            textview = target.get_child()
            buff = textview.get_buffer()
            textview.connect('key-press-event', on_text_view_n_press_event)
            textview.connect('paste-clipboard', self._on_textview_paste_clipboard, i)
            buff.connect('changed', self._on_target_changed, i)
            buff.connect('insert-text', self._on_target_insert_text, i)
            buff.connect('delete-range', self._on_target_delete_range, i)

            self._widgets['vbox_targets'].pack_start(target)
            self.targets.append(textview)

        for target, next_target in zip(self.targets, self.targets[1:] + [None]):
            target.connect('key-press-event', target_key_press_event, next_target)


    def _create_textbox(self, text='', editable=True, scroll_policy=gtk.POLICY_AUTOMATIC):
        textview = gtk.TextView()
        textview.set_editable(editable)
        textview.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        textview.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)
        textview.set_left_margin(2)
        textview.set_right_margin(2)
        textview.get_buffer().set_text(text or '')

        scrollwnd = gtk.ScrolledWindow()
        scrollwnd.set_policy(gtk.POLICY_NEVER, scroll_policy)
        scrollwnd.add(textview)

        return scrollwnd

    def _layout_update_notes(self, origin):
        if origin not in self._widgets['notes']:
            label = gtk.Label()
            label.set_line_wrap(True)

            self._widgets['vbox_middle'].pack_start(label)
            if origin == 'programmer':
                self._widgets['vbox_middle'].reorder_child(label, 0)
            elif origin == 'translator':
                self._widgets['vbox_middle'].reorder_child(label, 4)

            self._widgets['notes'][origin] = label

        if self.unit is None:
            note_text = u""
        else:
            note_text = self.unit.getnotes(origin) or u""

        if origin == "programmer" and len(note_text) < 15 and self.unit is not None and self.unit.getlocations():
            note_text += u"  " + u" ".join(self.unit.getlocations()[:3])

        self._widgets['notes'][origin].set_text(note_text)

        if note_text:
            self._widgets['notes'][origin].show_all()
        else:
            self._widgets['notes'][origin].hide()

    def _layout_update_sources(self):
        num_source_widgets = len(self.sources)

        if num_source_widgets < self.MAX_SOURCES:
            # Technically the condition above will only be True when num_target_widgets == 0, ie.
            # no target text boxes has been created yet.
            self._create_sources()
            num_source_widgets = len(self.sources)

        if self.unit is None:
            if num_source_widgets >= 1:
                # The above condition should *never* be False
                txtview = self.sources[0]
                txtview.get_buffer().set_text('')
                txtview.parent.show()
            for i in range(1, num_source_widgets):
                self.sources[i].parent.hide_all()
            return

        num_unit_sources = 1
        if self.unit.hasplural():
            num_unit_sources = len(self.unit.source.strings)

        for i in range(self.MAX_SOURCES):
            if i < num_unit_sources:
                sourcestr = ''
                if self.unit.hasplural():
                    sourcestr = self.unit.source.strings[i]
                elif i == 0:
                    sourcestr = self.unit.source
                else:
                    raise IndexError()

                self.sources[i].modify_font(rendering.get_source_font_description())
                self.sources[i].get_buffer().set_text(markup.escape(sourcestr))
                self.sources[i].parent.show_all()
                #logging.debug('Showing source #%d: %s' % (i, self.sources[i]))
            else:
                #logging.debug('Hiding source #%d: %s' % (i, self.sources[i]))
                self.sources[i].parent.hide_all()

    def _layout_update_context_info(self):
        if self.unit is None:
            if self._widgets['context_info']:
                self._widgets['context_info'].hide()
            return

        if self._widgets['context_info']:
            self._widgets['context_info'].show()
            self._widgets['context_info'].get_buffer().set_text(self.unit.getcontext() or u"")
        else:
            textbox = self._create_textbox(
                self.unit.getcontext(),
                editable=False,
                scroll_policy=gtk.POLICY_NEVER
            )
            textview = textbox.get_child()
            labelexpander = LabelExpander(textbox, lambda *args: self.unit.getcontext())

            self._widgets['vbox_middle'].pack_start(labelexpander)
            self._widgets['vbox_middle'].reorder_child(labelexpander, 2)
            self._widgets['context_info'] = textview

    def _layout_update_targets(self):
        num_target_widgets = len(self.targets)

        if num_target_widgets < self.MAX_TARGETS:
            # Technically the condition above will only be True when num_target_widgets == 0, ie.
            # no target text boxes has been created yet.
            self._create_targets()
            num_target_widgets = len(self.targets)

        if self.unit is None:
            if num_target_widgets >= 1:
                # The above condition should *never* be False
                txtview = self.targets[0]
                txtview.get_buffer().set_text('')
                txtview.parent.show_all()
            for i in range(1, num_target_widgets):
                self.targets[i].parent.hide_all()
            return

        num_unit_targets = 1
        nplurals = None
        if self.unit.hasplural():
            num_unit_targets = len(self.unit.target.strings)
            nplurals = self.controller.main_controller.lang_controller.target_lang.nplurals

        for i in range(self.MAX_TARGETS):
            if i < nplurals:
                # plural forms already in file
                if self.unit.hasplural() and i < num_unit_targets:
                    targetstr = self.unit.target.strings[i]
                elif i == 0:
                    targetstr = self.unit.target
                else:
                    targetstr = ''

                self.targets[i].modify_font(rendering.get_target_font_description())
                self.targets[i].get_buffer().set_text(markup.escape(targetstr))
                self.targets[i].parent.show_all()
                #logging.debug('Showing target #%d: %s' % (i, self.targets[i]))
            else:
                # outside plural range
                #logging.debug('Hiding target #%d: %s' % (i, self.targets[i]))
                self.targets[i].parent.hide_all()

    def _layout_update_fuzzy(self):
        if not self._widgets['fuzzy']:
            fuzzy = gtk.CheckButton(label=_('F_uzzy'))
            # FIXME: not allowing focus will probably raise various issues related to keyboard accesss.
            fuzzy.set_property("can-focus", False)
            fuzzy.connect('toggled', self._on_fuzzy_toggled)
            self._widgets['vbox_right'].pack_end(fuzzy, expand=False, fill=False)
            self._widgets['fuzzy'] = fuzzy

        if self.unit is not None:
            self._widgets['fuzzy'].show()
            self._widgets['fuzzy'].set_active(self.unit.isfuzzy())


    # EVENT HANLDERS #
    def _on_fuzzy_toggled(self, toggle_button, *args):
        if self.unit is None:
            return
        self.unit.markfuzzy(toggle_button.get_active())
        self.modified()

    def _on_key_press_event(self, _widget, event, *_args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            self.must_advance = True
            self.emit('unit-done', self.unit)
            self.editing_done()
            return True
        return False

    def _on_target_changed(self, buffer, index):
        newtext = self.get_target_n(index)
        if self.unit.hasplural():
            nplurals = self.controller.main_controller.lang_controller.target_lang.nplurals
            # FIXME: The following two lines are necessary because self.unit.target always
            # returns a new multistring, so you can't assign to an index directly.
            target = self.unit.target.strings
            if len(target) < nplurals:
                # pad the target with empty strings
                target += (nplurals - len(target)) * [u""]
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

        #logging.debug('emit("insert-text", old_text="%s", ins_text="%s", offset=%d, target_num=%d)' % (old_text, ins_text, offset, target_num))
        self.emit('insert-text', old_text, ins_text, offset, target_num)

    def _on_target_delete_range(self, buff, start_iter, end_iter, target_num):
        cursor_iter = buff.get_iter_at_mark(buff.get_insert())
        cursor_pos = len(buff.get_text(buff.get_start_iter(), cursor_iter))
        old_text = buff.get_text(buff.get_start_iter(), buff.get_end_iter())
        start_offset = len(buff.get_text(buff.get_start_iter(), start_iter)) # FIXME: Isn't there a better way to do this?
        end_offset = len(buff.get_text(buff.get_start_iter(), end_iter)) # FIXME: Isn't there a better way to do this?

        #logging.debug('emit("delete-text", old_text="%s", start_offset=%d, end_offset=%d, cursor_pos=%d, target_num=%d)' % (old_text, start_offset, end_offset, cursor_pos, target_num))
        self.emit('delete-text', old_text, start_offset, end_offset, cursor_pos, target_num)

    def _on_textview_paste_clipboard(self, textview, target_num):
        buff = textview.get_buffer()
        old_text = buff.get_text(buff.get_start_iter(), buff.get_end_iter())
        ins_iter  = buff.get_iter_at_mark(buff.get_insert())
        selb_iter = buff.get_iter_at_mark(buff.get_selection_bound())

        offsets = {
            'insert_offset': ins_iter.get_offset(),
            'selection_offset': selb_iter.get_offset()
        }

        #logging.debug('emit("paste-start", old_text="%s", offsets=%d, target_num=%d)' % (old_text, offsets, target_num))
        self.emit('paste-start', old_text, offsets, target_num)
