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

import gobject
import gtk
from gobject import SIGNAL_RUN_FIRST, SIGNAL_RUN_LAST, TYPE_PYOBJECT

from translate.misc.typecheck import accepts, Self, IsOneOf
from translate.storage.placeables import StringElem, parse as elem_parse
from translate.lang import data

from virtaal.views import placeablesguiinfo


class TextBox(gtk.TextView):
    """
    A C{gtk.TextView} extended to work with our nifty L{StringElem} parsed
    strings.
    """

    __gtype_name__ = 'TextBox'
    __gsignals__ = {
        'after-apply-gui-info':  (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'before-apply-gui-info': (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'element-selected':  (SIGNAL_RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'key-pressed':       (SIGNAL_RUN_LAST,  bool, (TYPE_PYOBJECT, str)),
        'text-deleted':      (SIGNAL_RUN_LAST,  bool, (int, int, TYPE_PYOBJECT, TYPE_PYOBJECT, int, TYPE_PYOBJECT)),
        'text-inserted':     (SIGNAL_RUN_LAST,  bool, (TYPE_PYOBJECT, int, TYPE_PYOBJECT)),
    }

    SPECIAL_KEYS = {
        'alt-down':  [(gtk.keysyms.Down,  gtk.gdk.MOD1_MASK)],
        'alt-left':  [(gtk.keysyms.Left,  gtk.gdk.MOD1_MASK)],
        'alt-right': [(gtk.keysyms.Right, gtk.gdk.MOD1_MASK)],
        'enter':     [(gtk.keysyms.Return, 0), (gtk.keysyms.KP_Enter, 0)],
    }
    """A table of name-keybinding mappings. The name (key) is passed as the
    second parameter to the 'key-pressed' event."""
    unselectables = [StringElem]
    """A list of classes that should not be selectable with Alt+Left or Alt+Right."""

    # INITIALIZERS #
    def __init__(self, main_controller, text=None, selector_textbox=None, role=None):
        """Constructor.
        @type  main_controller: L{virtaal.controllers.main_controller}
        @param main_controller: The main controller instance.
        @type  text: String
        @param text: The initial text to set in the new text box. Optional.
        @type  selector_textbox: C{TextBox}
        @param selector_textbox: The text box in which placeable selection
            (@see{select_elem}) should happen. Optional."""
        super(TextBox, self).__init__()
        self.buffer = self.get_buffer()
        self.elem = None
        self.main_controller = main_controller
        self.role = role
        self.selector_textbox = selector_textbox or self
        self.selected_elem = None
        self.selected_elem_index = None
        self._suggestion = None
        self.__connect_default_handlers()
        self.placeables_controller = main_controller.placeables_controller
        if self.placeables_controller is None:
            self.__controller_connect_id = main_controller.connect('controller-registered', self.__on_controller_register)
        if text:
            self.set_text(text)

    def __connect_default_handlers(self):
        self.connect('button-press-event', self._on_event_remove_suggestion)
        self.connect('focus-out-event', self._on_event_remove_suggestion)
        self.connect('key-press-event', self._on_key_pressed)
        self.connect('move-cursor', self._on_event_remove_suggestion)
        self.buffer.connect('insert-text', self._on_insert_text)
        self.buffer.connect('delete-range', self._on_delete_range)


    def _get_suggestion(self):
        return self._suggestion
    def _set_suggestion(self, value):
        if value is None:
            self.hide_suggestion()
            self._suggestion = None
            return

        if not (isinstance(value, dict) and \
                'text'   in value and value['text'] and \
                'offset' in value and value['offset'] >= 0):
            raise ValueError('invalid suggestion dictionary: %s' % (value))

        if self.suggestion_is_visible():
            self.suggestion = None
        self._suggestion = value
        self.show_suggestion()
    suggestion = property(_get_suggestion, _set_suggestion)

    # OVERRIDDEN METHODS #
    def get_stringelem(self):
        if self.elem is None:
            return None
        return elem_parse(self.elem, self.placeables_controller.get_parsers_for_textbox(self))

    def get_text(self, start_iter=None, end_iter=None):
        """Return the text rendered in this text box.
            Uses C{gtk.TextBuffer.get_text()}."""
        if isinstance(start_iter, int):
            start_iter = self.buffer.get_iter_at_offset(start_iter)
        if isinstance(end_iter, int):
            end_iter = self.buffer.get_iter_at_offset(end_iter)
        if start_iter is None:
            start_iter = self.buffer.get_start_iter()
        if end_iter is None:
            end_iter = self.buffer.get_end_iter()
        return data.forceunicode(self.buffer.get_text(start_iter, end_iter))

    @accepts(Self(), [[IsOneOf(StringElem, str, unicode)]])
    def set_text(self, text):
        """Set the text rendered in this text box.
            Uses C{gtk.TextBuffer.set_text()}.
            @type  text: str|unicode|L{StringElem}
            @param text: The text to render in this text box."""
        if not isinstance(text, StringElem):
            text = StringElem(text)

        if self.elem is None:
            self.elem = StringElem(u'')

        if text is not self.elem:
            # If text is self.elem, we are busy with a refresh and we should remember the selected element.
            self.selected_elem = None
            self.selected_elem_index = None

            if self.placeables_controller:
                self.elem.sub = [elem_parse(text, self.placeables_controller.get_parsers_for_textbox(self))]
            else:
                self.elem.sub = [text]
            self.elem.prune()

        self.update_tree(self.elem)


    # METHODS #
    @accepts(Self(), [StringElem])
    def add_default_gui_info(self, elem):
        """Add default GUI info to string elements in the tree that does not
            have any GUI info.

            Only leaf nodes are (currently) extended with a C{StringElemGUI}
            (or sub-class) instance. Other nodes has C{gui_info} set to C{None}.

            @type  elem: StringElem
            @param elem: The root of the string element tree to add default
                GUI info to.
            """
        if not isinstance(elem, StringElem):
            return

        if not hasattr(elem, 'gui_info') or not elem.gui_info:
            if not self.placeables_controller:
                return
            elem.gui_info = self.placeables_controller.get_gui_info(elem)(elem=elem, textbox=self)

        for sub in elem.sub:
            self.add_default_gui_info(sub)

    @accepts(Self(), [StringElem, bool])
    def apply_gui_info(self, elem, include_subtree=True):
        offset = self.elem.gui_info.index(elem)
        #logging.debug('offset for %s: %d' % (repr(elem), offset))
        if offset >= 0:
            #logging.debug('[%s] at offset %d' % (unicode(elem).encode('utf-8'), offset))
            self.emit('before-apply-gui-info', elem)

            if getattr(elem, 'gui_info', None):
                start_index = offset
                end_index = offset + elem.gui_info.length()
                interval = end_index - start_index
                for tag, tag_start, tag_end in elem.gui_info.create_tags():
                    if tag is None:
                        continue
                    # Calculate tag start and end offsets
                    if tag_start is None:
                        tag_start = 0
                    if tag_end is None:
                        tag_end = end_index
                    if tag_start < 0:
                        tag_start += interval + 1
                    else:
                        tag_start += start_index
                    if tag_end < 0:
                        tag_end += end_index + 1
                    else:
                        tag_end += start_index
                    if tag_start < start_index:
                        tag_start = start_index
                    if tag_end > end_index:
                        tag_end = end_index

                    iters = (
                        self.buffer.get_iter_at_offset(tag_start),
                        self.buffer.get_iter_at_offset(tag_end)
                    )
                    #logging.debug('  Apply tag at interval (%d, %d) [%s]' % (tag_start, tag_end, self.get_text(*iters)))

                    if not include_subtree or \
                            elem.gui_info.fg != placeablesguiinfo.StringElemGUI.fg or \
                            elem.gui_info.bg != placeablesguiinfo.StringElemGUI.bg:
                        self.buffer.get_tag_table().add(tag)
                        self.buffer.apply_tag(tag, iters[0], iters[1])

        if include_subtree:
            for sub in elem.sub:
                if isinstance(sub, StringElem):
                    self.apply_gui_info(sub)

        self.emit('after-apply-gui-info', elem)

    def hide_suggestion(self):
        if not self.suggestion_is_visible():
            return
        selection = self.buffer.get_selection_bounds()
        if not selection:
            return

        self.buffer.handler_block_by_func(self._on_delete_range)
        self.buffer.delete(*selection)
        self.buffer.handler_unblock_by_func(self._on_delete_range)

    @accepts(Self(), [StringElem])
    def insert_translation(self, elem):
        selection = self.buffer.get_selection_bounds()
        if selection:
            self.buffer.delete(*selection)
        cursor_pos = self.buffer.props.cursor_position
        widget = elem.gui_info.get_insert_widget()
        if widget:
            cursor_iter = self.buffer.get_iter_at_offset(cursor_pos)
            anchor = self.buffer.create_child_anchor(cursor_iter)
            # It is necessary to recreate cursor_iter becuase, for some inexplicable reason,
            # the Gtk guys thought it acceptable to have create_child_anchor() above CHANGE
            # THE PARAMETER ITER'S VALUE! But only in some cases, while the moon is 73.8% full
            # and it's after 16:33. Documenting this is obviously also too much to ask.
            # Nevermind the fact that there isn't simply a gtk.TextBuffer.remove_anchor() method
            # or something similar. Why would you want to remove anything from a TextView that
            # you have added anyway!?
            # It's crap like this that'll make me ditch Gtk.
            cursor_iter = self.buffer.get_iter_at_offset(cursor_pos)
            self.add_child_at_anchor(widget, anchor)
            widget.show_all()
            if callable(getattr(widget, 'inserted', None)):
                widget.inserted(cursor_iter, anchor)
        else:
            translation = elem.translate()
            if isinstance(translation, StringElem):
                self.add_default_gui_info(translation)
                insert_offset = self.elem.gui_info.gui_to_tree_index(cursor_pos)
                self.elem.insert(insert_offset, translation)
                self.elem.prune()
                cursor_pos += translation.gui_info.length()

                self.emit('text-inserted', unicode(translation), insert_offset, self.elem)
            else:
                self.buffer.insert_at_cursor(translation)
                cursor_pos += len(translation)
            self.refresh(cursor_pos=cursor_pos)

    @accepts(Self(), [int])
    def move_elem_selection(self, offset):
        if self.selector_textbox.selected_elem_index is None:
            if offset <= 0:
                self.selector_textbox.select_elem(offset=offset)
            else:
                self.selector_textbox.select_elem(offset=offset-1)
        else:
            self.selector_textbox.select_elem(offset=self.selector_textbox.selected_elem_index + offset)

    def refresh(self, cursor_pos=-1, preserve_selection=True):
        """Refresh the text box by setting its text to the current text."""
        selection = [itr.get_offset() for itr in self.buffer.get_selection_bounds()]

        if self.elem is not None:
            self.elem.prune()
            self.set_text(self.elem)
        else:
            self.set_text(self.get_text())

        if type(cursor_pos) is int and cursor_pos >= 0:
            if not self.buffer.get_selection_bounds():
                self.buffer.place_cursor(self.buffer.get_iter_at_offset(cursor_pos))
        elif type(cursor_pos) is gtk.TreeIter:
            if not self.buffer.get_selection_bounds():
                self.buffer.place_cursor(cursor_pos)

        if preserve_selection and selection:
            self.buffer.select_range(
                self.buffer.get_iter_at_offset(selection[0]),
                self.buffer.get_iter_at_offset(selection[1]),
            )

    @accepts(Self(), [[StringElem, None], [int, None]])
    def select_elem(self, elem=None, offset=None):
        if elem is not None and offset is not None:
            raise ValueError('Only one of "elem" or "offset" may be specified.')

        if elem is None and offset is None:
            # Clear current selection
            if self.selected_elem is not None:
                #logging.debug('Selected item *was* %s' % (repr(self.selected_elem)))
                self.selected_elem.gui_info = None
                self.add_default_gui_info(self.selected_elem)
                self.selected_elem = None
            self.selected_elem_index = None
            return

        filtered_elems = [e for e in self.elem.depth_first() if e.__class__ not in self.unselectables]
        if not filtered_elems:
            return

        if elem is None and offset is not None:
            return self.select_elem(elem=filtered_elems[offset % len(filtered_elems)])

        if not elem in filtered_elems:
            return

        # Reset the default tag for the previously selected element
        if self.selected_elem is not None:
            self.selected_elem.gui_info = None
            self.add_default_gui_info(self.selected_elem)

        i = 0
        for fe in filtered_elems:
            if fe is elem:
                break
            i += 1
        self.selected_elem_index = i
        self.selected_elem = elem
        #logging.debug('Selected element: %s (%s)' % (repr(self.selected_elem), unicode(self.selected_elem)))
        if not hasattr(elem, 'gui_info') or not elem.gui_info:
            elem.gui_info = placeablesguiinfo.StringElemGUI(elem, self, fg='#000000', bg='#90ee90')
        else:
            elem.gui_info.fg = '#000000'
            elem.gui_info.bg = '#90ee90'
        self.apply_gui_info(self.elem, include_subtree=False)
        self.apply_gui_info(self.elem)
        self.apply_gui_info(elem, include_subtree=False)
        cursor_offset = self.elem.find(self.selected_elem) + len(self.selected_elem)
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(cursor_offset))
        self.emit('element-selected', self.selected_elem)

    def show_suggestion(self, suggestion=None):
        if isinstance(suggestion, dict):
            self.suggestion = suggestion
        if self.suggestion is None:
            return
        iters = (self.buffer.get_iter_at_offset(self.suggestion['offset']),)
        self.buffer.handler_block_by_func(self._on_insert_text)
        self.buffer.insert(iters[0], self.suggestion['text'])
        self.buffer.handler_unblock_by_func(self._on_insert_text)
        iters = (
            self.buffer.get_iter_at_offset(self.suggestion['offset']),
            self.buffer.get_iter_at_offset(
                self.suggestion['offset'] + len(self.suggestion['text'])
            )
        )
        self.buffer.select_range(*iters)

    def suggestion_is_visible(self):
        """Checks whether the current text suggestion is visible."""
        selection = self.buffer.get_selection_bounds()
        if not selection or self.suggestion is None:
            return False
        start_offset = selection[0].get_offset()
        text = self.buffer.get_text(*selection)
        return self.suggestion['text'] and \
                self.suggestion['text'] == text and \
                self.suggestion['offset'] >= 0 and \
                self.suggestion['offset'] == start_offset

    @accepts(Self(), [[StringElem, basestring, None]])
    def update_tree(self, text=None):
        if not self.placeables_controller:
            return
        if not isinstance(text, StringElem):
            return
        if self.elem is None:
            self.elem = StringElem(u'')
        if text is not self.elem:
            self.elem.sub = [text]
            self.elem.prune()

        self.add_default_gui_info(self.elem)

        self.buffer.handler_block_by_func(self._on_delete_range)
        self.buffer.handler_block_by_func(self._on_insert_text)
        self.elem.gui_info.render()
        self.show_suggestion()
        self.buffer.handler_unblock_by_func(self._on_delete_range)
        self.buffer.handler_unblock_by_func(self._on_insert_text)

        tagtable = self.buffer.get_tag_table()
        def remtag(tag, data):
            tagtable.remove(tag)
        # FIXME: The following line caused the program to segfault, so it's removed (for now).
        #tagtable.foreach(remtag)
        # At this point we have a tree of string elements with GUI info.
        self.apply_gui_info(text)

    def __delayed_refresh(self, cursor_pos=-1):
        if cursor_pos < 0:
            cursor_pos = self.buffer.props.cursor_position
        gobject.idle_add(self.refresh, cursor_pos)


    # EVENT HANDLERS #
    def __on_controller_register(self, main_controller, controller):
        if controller is main_controller.placeables_controller:
            self.placeables_controller = controller
            main_controller.disconnect(self.__controller_connect_id)

    def _on_delete_range(self, buffer, start_iter, end_iter):
        if self.elem is None:
            return

        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
        text = data.forceunicode(text)
        start_offset = start_iter.get_offset()
        end_offset = end_iter.get_offset()

        if text[start_offset:end_offset] == u'\n' and text[:start_offset].endswith(u'\\n'):
            start_iter.set_offset(start_offset-2)

        start_elem = self.elem.gui_info.elem_at_offset(start_offset)
        if start_elem is None or (end_offset - start_offset) == 1 and start_iter.get_child_anchor():
            return
        start_elem_len = start_elem.gui_info.length()
        start_elem_offset = self.elem.gui_info.index(start_elem)

        end_elem = self.elem.gui_info.elem_at_offset(end_offset)
        if end_elem is not None:
            # end_elem can be None if end_offset == self.elem.gui_info.length()
            end_elem_len = end_elem.gui_info.length()
            end_elem_offset = self.elem.gui_info.index(end_elem)
        else:
            end_elem_len = 0
            end_elem_offset = self.elem.gui_info.length()

        #logging.debug('pre-checks: %s[%d:%d]' % (repr(self.elem), start_offset, end_offset))
        #logging.debug('start_elem_offset= %d\tend_elem_offset= %d' % (start_elem_offset, end_elem_offset))
        #logging.debug('start_elem_len   = %d\tend_elem_len   = %d' % (start_elem_len, end_elem_len))
        #logging.debug('start_offset     = %d\tend_offset     = %d' % (start_offset, end_offset))

        if start_elem is not None and not start_elem.iseditable:
            if start_offset+1 == end_offset:
                # A single character delete on non-editable placeables are only valid at the head or tail.
                if start_offset == start_elem_offset:
                    # Delete the first character of a non-editable placeable. This is most likely because the
                    # user pressed delete with the cursor before the placeable.
                    end_iter.set_offset(start_elem_offset + start_elem_len)
                elif start_elem_offset + start_elem_len == end_offset:
                    # Backspace was pressed with the cursor positioned right after the placeable.
                    start_iter.set_offset(start_elem_offset)
            elif start_elem_offset + start_elem_len <= end_elem_offset:
                start_iter.set_offset(start_elem_offset)
        if end_elem is not None and not end_elem.iseditable:
            if start_elem_offset + start_elem_len < end_offset:
                end_iter.set_offset(end_elem_offset + end_elem_len)

        #logging.debug('%s[%d] >===> %s[%d]' % (repr(start_elem), start_iter.get_offset(), repr(end_elem), end_iter.get_offset()))

        cursor_pos = self.buffer.props.cursor_position

        start_tree_offset = self.elem.gui_info.gui_to_tree_index(start_iter.get_offset())
        end_tree_offset = self.elem.gui_info.gui_to_tree_index(end_iter.get_offset())
        deleted, parent = self.elem.delete_range(start_tree_offset, end_tree_offset)

        self.emit('text-deleted', start_iter.get_offset(), end_iter.get_offset(), deleted, parent, cursor_pos, self.elem)
        self.__delayed_refresh(start_iter.get_offset())
        self.buffer.stop_emission('delete-range')

    def _on_insert_text(self, buffer, iter, ins_text, length):
        if self.elem is None:
            return

        ins_text = data.forceunicode(ins_text[:length])
        buff_offset = iter.get_offset()
        gui_info = self.elem.gui_info
        left = gui_info.elem_at_offset(buff_offset-1)
        right = gui_info.elem_at_offset(buff_offset)

        #logging.debug('%s |"%s"| %s  ||| %s[%d]' % (repr(left), ins_text, repr(right), repr(self.elem), buff_offset))
        succeeded = False
        if not (left is None and right is None) and (left is not right or not unicode(left)):
            succeeded = self.elem.insert_between(left, right, ins_text)
            #logging.debug('self.elem.insert_between(%s, %s, "%s"): %s' % (repr(left), repr(right), ins_text, succeeded))

        if not succeeded:
            offset = gui_info.gui_to_tree_index(buff_offset)
            succeeded = self.elem.insert(offset, ins_text)
            #logging.debug('self.elem.insert(%d, "%s"): %s' % (offset, ins_text, succeeded))

        if succeeded:
            self.elem.prune()
            self.__delayed_refresh(self.buffer.props.cursor_position+len(ins_text))
            #logging.debug('text-inserted: %s@%d of %s' % (ins_text, iter.get_offset(), repr(self.elem)))
            self.emit('text-inserted', ins_text, iter.get_offset(), self.elem)
        else:
            self.buffer.stop_emission('insert-text')

    def _on_key_pressed(self, widget, event, *args):
        evname = None

        if self.suggestion_is_visible():
            if event.keyval == gtk.keysyms.Tab:
                self.hide_suggestion()
                self.buffer.insert(
                    self.buffer.get_iter_at_offset(self.suggestion['offset']),
                    self.suggestion['text']
                )
                self.suggestion = None
                return True
            self.suggestion = None

        # Uncomment the following block to get nice textual logging of key presses in the textbox
        #keyname = '<unknown>'
        #for attr in dir(gtk.keysyms):
        #    if getattr(gtk.keysyms, attr) == event.keyval:
        #        keyname = attr
        #statenames = []
        #for attr in [a for a in ('MOD1_MASK', 'MOD2_MASK', 'MOD3_MASK', 'MOD4_MASK', 'MOD5_MASK', 'CONTROL_MASK', 'SHIFT_MASK', 'RELEASE_MASK', 'LOCK_MASK', 'SUPER_MASK', 'HYPER_MASK', 'META_MASK')]:
        #    if event.state & getattr(gtk.gdk, attr):
        #        statenames.append(attr)
        #statenames = '|'.join(statenames)
        #logging.debug('Key pressed: %s (%s)' % (keyname, statenames))
        #logging.debug('state (raw): %x' % (event.state,))

        # Ignore numlock and weird state sometimes present with Arabic
        # keyboard layout. See bug 926.
        trimmed_state = event.state & ~ (gtk.gdk.MOD2_MASK | gtk.gdk.LEAVE_NOTIFY_MASK)

        for name, keyslist in self.SPECIAL_KEYS.items():
            for keyval, state in keyslist:
                if event.keyval == keyval and (trimmed_state == state):
                    evname = name

        if evname == 'alt-left':
            self.move_elem_selection(-1)
        elif evname == 'alt-right':
            self.move_elem_selection(1)

        return self.emit('key-pressed', event, evname)

    def _on_event_remove_suggestion(self, *args):
        self.suggestion = None
