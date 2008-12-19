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
import gtk.gdk
import logging
import re

from virtaal.controllers import Cursor

from basemode import BaseMode


class SearchMatch(object):
    """Just a small data structure that represents a search match."""

    # INITIALIZERS #
    def __init__(self, unit, part='target', part_n=0, start=0, end=0):
        self.unit   = unit
        self.part   = part
        self.part_n = part_n
        self.start  = start
        self.end    = end

    # ACCESSORS #
    def get_getter(self):
        if self.part == 'target':
            def getter():
                return self.unit.target.strings[self.part_n]
            return getter
        elif self.part == 'source':
            def getter():
                return self.unit.source.strings[self.part_n]
            return getter
        elif self.part == 'notes':
            def getter():
                return self.unit.getnotes()[self.part_n]
            return getter
        elif self.part == 'locations':
            def getter():
                return self.unit.getlocations()[self.part_n]
            return getter

    def get_setter(self):
        if self.part == 'target':
            def setter(value):
                strings = self.unit.target.strings
                strings[self.part_n] = value
                self.unit.target = strings
            return setter

    # METHODS #
    def select(self, main_controller):
        """Select this match in the GUI."""
        main_controller.select_unit(self.unit)
        view = main_controller.unit_controller.view

        # Wait for SearchMode to finish with its highlighting and stuff, and then we do...
        if self.part == 'target':
            def select_match_text():
                target = view.targets[self.part_n]
                target.grab_focus()
                buff = target.get_buffer()
                start_iter = buff.get_iter_at_offset(self.start)
                end_iter = buff.get_iter_at_offset(self.end)
                buff.select_range(end_iter, start_iter)
                return False
        elif self.part == 'source':
            def select_match_text():
                source = view.sources[self.part_n]
                source.grab_focus()
                buff = source.get_buffer()
                start_iter = buff.get_iter_at_offset(self.start)
                end_iter = buff.get_iter_at_offset(self.end)
                buff.select_range(end_iter, start_iter)
                return False
        # TODO: Implement for 'notes' and 'locations' parts
        gobject.idle_add(select_match_text)

    def replace(self, replace_str, main_controller=None):
        unit_controller = main_controller.unit_controller
        # Using unit_controller directly is a hack to make sure that the replacement changes are immediately displayed.
        if self.part != 'target':
            return
        strings = self.unit.target.strings
        string_n = strings[self.part_n]
        if unit_controller is None:
            strings[self.part_n] = string_n[:self.start] + replace_str + string_n[self.end:]
            self.unit.target = strings
        else:
            main_controller.select_unit(self.unit)
            unit_controller.set_unit_target(self.part_n, string_n[:self.start] + replace_str + string_n[self.end:])

    # SPECIAL METHODS #
    def __str__(self):
        start, end = self.start, self.end
        if start < 3:
            start = 3
        if end > len(self.get_getter()()) - 3:
            end = len(self.get_getter()()) - 3
        matchpart = self.get_getter()()[start-2:end+2]
        return '<SearchMatch "%s" part=%s[%d] start=%d end=%d>' % (matchpart, self.part, self.part_n, self.start, self.end)

    def __repr__(self):
        return str(self)


class SearchMode(BaseMode):
    """Search mode - Includes only units matching the given search term."""

    name = 'Search'
    display_name = _("Search")
    widgets = []

    SEARCH_DELAY = 500

    # INITIALIZERS #
    def __init__(self, controller):
        """Constructor.
            @type  controller: virtaal.controllers.ModeController
            @param controller: The ModeController that managing program modes."""
        self.controller = controller

        self._create_widgets()
        self._setup_key_bindings()

        self.matches = []
        self.re_search = None
        self.select_first_match = True
        self._search_timeout = 0
        self._unit_modified_id = 0

    def _create_widgets(self):
        # Widgets for search functionality (in first row)
        self.ent_search = gtk.Entry()
        self.ent_search.connect('changed', self._on_search_text_changed)
        self.ent_search.connect('activate', self._on_entry_activate)
        self.btn_search = gtk.Button(_('Search'))
        self.btn_search.connect('clicked', self._on_search_clicked)
        self.chk_casesensitive = gtk.CheckButton(_('_Case sensitive'))
        self.chk_casesensitive.connect('toggled', self._refresh_proxy)
        self.chk_regex = gtk.CheckButton(_("_Regular expression"))
        self.chk_regex.connect('toggled', self._refresh_proxy)

        # Widgets for replace (second row)
        self.lbl_replace = gtk.Label(_('Replace with'))
        self.ent_replace = gtk.Entry()
        self.btn_replace = gtk.Button(_('Replace'))
        self.btn_replace.connect('clicked', self._on_replace_clicked)
        self.chk_replace_all = gtk.CheckButton(_('Replace _All'))

        self.widgets = [
            self.ent_search, self.btn_search, self.chk_casesensitive, self.chk_regex,
            self.lbl_replace, self.ent_replace, self.btn_replace, self.chk_replace_all
        ]

        self.default_base = gtk.widget_get_default_style().base[gtk.STATE_NORMAL]
        self.default_text = gtk.widget_get_default_style().text[gtk.STATE_NORMAL]

    def _setup_key_bindings(self):
        gtk.accel_map_add_entry("<Virtaal>/Edit/Search", gtk.keysyms.F3, 0)
        gtk.accel_map_add_entry("<Virtaal>/Edit/Search Ctrl+F", gtk.keysyms.F, gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<Virtaal>/Edit/Search: Next", gtk.keysyms.G, gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<Virtaal>/Edit/Search: Previous", gtk.keysyms.G, gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK)

        self.accel_group = gtk.AccelGroup()
        self.accel_group.connect_by_path("<Virtaal>/Edit/Search", self._on_start_search)
        self.accel_group.connect_by_path("<Virtaal>/Edit/Search Ctrl+F", self._on_start_search)
        self.accel_group.connect_by_path("<Virtaal>/Edit/Search: Next", self._on_search_next)
        self.accel_group.connect_by_path("<Virtaal>/Edit/Search: Previous", self._on_search_prev)

        self.controller.main_controller.view.add_accel_group(self.accel_group)


    # METHODS #
    def get_matches(self, units):
        if not self.ent_search.get_text():
            return []

        searchstring = self.ent_search.get_text().decode('utf-8')
        searchparts = ('source', 'target')
        ignorecase = not self.chk_casesensitive.get_active()
        useregexp = self.chk_regex.get_active()
        flags = re.LOCALE | re.MULTILINE | re.UNICODE

        if ignorecase:
            flags |= re.IGNORECASE
        if not useregexp:
            searchstring = re.escape(searchstring)
        self.re_search = re.compile(u'(%s)' % (searchstring), flags)

        matches = []

        for unit in units:
            if 'target' in searchparts:
                part = 'target'
                part_n = 0
                for target in unit.target.strings:
                    for matchobj in self.re_search.finditer(target):
                        matches.append(
                            SearchMatch(unit, part=part, part_n=part_n, start=matchobj.start(), end=matchobj.end())
                        )
                    part_n += 1

            if 'source' in searchparts:
                part = 'source'
                part_n = 0
                for source in unit.source.strings:
                    for matchobj in self.re_search.finditer(source):
                        matches.append(
                            SearchMatch(unit, part=part, part_n=part_n, start=matchobj.start(), end=matchobj.end())
                        )
                    part_n += 1

            if 'notes' in searchparts:
                part = 'notes'
                part_n = 0
                for note in unit.getnotes():
                    for matchobj in self.re_search.finditer(note):
                        matches.append(
                            SearchMatch(unit, part=part, part_n=part_n, start=matchobj.start(), end=matchobj.end())
                        )
                    part_n += 1

            if 'locations' in searchparts:
                part = 'locations'
                part_n = 0
                for loc in unit.getlocations():
                    for matchobj in self.re_search.finditer(loc):
                        matches.append(
                            SearchMatch(unit, part=part, part_n=part_n, start=matchobj.start(), end=matchobj.end())
                        )
                    part_n += 1

        return matches

    def selected(self):
        # XXX: Assumption: This method is called when a new file is loaded and that is
        #      why we keep a reference to the store's cursor.
        self.storecursor = self.controller.main_controller.store_controller.cursor
        if not self.storecursor or not self.storecursor.model:
            return

        self._add_widgets()
        self._connect_highlighting()
        if not self.ent_search.get_text():
            self.storecursor.indices = self.storecursor.model.stats['total']
        else:
            self.update_search()

        def grab_focus():
            self.ent_search.grab_focus()
            return False

        # FIXME: The following line is a VERY UGLY HACK, but at least it works.
        gobject.timeout_add(100, grab_focus)

    def update_search(self):
        self.matches = self.get_matches(self.storecursor.model.get_units())
        self.matchcursor = Cursor(self.matches, range(len(self.matches)))
        self._recalculate_match_indexes()

    def unselected(self):
        # TODO: Unhightlight the previously selected unit
        if getattr(self, '_signalid_cursor_changed', ''):
            self.storecursor.disconnect(self._signalid_cursor_changed)

        if self._unit_modified_id:
            self.controller.main_controller.unit_controller.disconnect(self._unit_modified_id)
            self._unit_modified_id = 0

        self.matches = []

    def _add_widgets(self):
        table = self.controller.view.mode_box

        table.attach(self.ent_search, 2, 3, 0, 1)
        table.attach(self.btn_search, 3, 4, 0, 1)
        table.attach(self.chk_casesensitive, 4, 5, 0, 1)
        table.attach(self.chk_regex, 5, 6, 0, 1)

        table.attach(self.lbl_replace, 1, 2, 1, 2)
        table.attach(self.ent_replace, 2, 3, 1, 2)
        table.attach(self.btn_replace, 3, 4, 1, 2)
        table.attach(self.chk_replace_all, 4, 5, 1, 2)

        table.show_all()

    def _connect_highlighting(self):
        self._signalid_cursor_changed = self.storecursor.connect('cursor-changed', self._on_cursor_changed)

    def _get_matches_for_unit(self, unit):
        return [match for match in self.matches if match.unit is unit]

    def _highlight_matches(self):
        self._unhighlight_previous_matches()

        if self.re_search is None:
            return

        unitview = self.controller.main_controller.unit_controller.view
        self._prev_unitview = unitview
        for textview in unitview.sources + unitview.targets:
            buff = textview.get_buffer()
            buffstr = buff.get_text(buff.get_start_iter(), buff.get_end_iter()).decode('utf-8')

            # First make sure that the current buffer contains a highlighting tag.
            # Because a gtk.TextTag can only be associated with one gtk.TagTable,
            # we make copies (created by _make_highlight_tag()) to add to all
            # TagTables. If the tag is already added to a given table, a
            # ValueError is raised which we can safely ignore.
            try:
                buff.get_tag_table().add(self._make_highlight_tag())
            except ValueError:
                pass

            select_iters = []
            for match in self.re_search.finditer(buffstr):
                start_iter, end_iter = buff.get_iter_at_offset(match.start()), buff.get_iter_at_offset(match.end())
                buff.apply_tag_by_name('highlight', start_iter, end_iter)

                if textview in unitview.targets and not select_iters and self.select_first_match:
                    select_iters = [start_iter, end_iter]

            if select_iters:
                buff.select_range(select_iters[1], select_iters[0])
                return

    def _make_highlight_tag(self):
        tag = gtk.TextTag(name='highlight')
        tag.set_property('background', 'yellow')
        tag.set_property('foreground', 'black')
        return tag

    def _move_match(self, offset):
        if getattr(self, 'matchcursor', None) is None:
            self.update_search()
            self._move_match(offset)
            return

        old_match_index = self.matchcursor.index
        if not self.matches or old_match_index != self.matchcursor.index:
            self.update_search()
            return

        self.matchcursor.move(offset)
        self.matches[self.matchcursor.index].select(self.controller.main_controller)

    def _recalculate_match_indexes(self):
        store_units = self.storecursor.model.get_units()
        indexes = [store_units.index(match.unit) for match in self.matches]
        indexes = list(set(indexes)) # Remove duplicates
        indexes.sort()

        logging.debug('Search text: %s (%d matches)' % (self.ent_search.get_text(), len(indexes)))

        if indexes:
            self.ent_search.modify_base(gtk.STATE_NORMAL, self.default_base)
            self.ent_search.modify_text(gtk.STATE_NORMAL, self.default_text)

            self.storecursor.indices = indexes
            # Select initial match for in the current unit.
            match_index = 0
            selected_unit = self.storecursor.model[self.storecursor.index]
            for match in self.matches:
                if match.unit is selected_unit:
                    break
                match_index += 1
            self.matchcursor.index = match_index
        else:
            self.ent_search.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('#f66'))
            self.ent_search.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#fff'))
            self.re_search = None
            # Act like the "Default" mode...
            self.storecursor.indices = self.storecursor.model.stats['total']
        self._highlight_matches()

        def grabfocus():
            self.ent_search.grab_focus()
            self.ent_search.set_position(-1)
            return False
        gobject.idle_add(grabfocus)

    def _replace_all(self):
        for match in self.matches:
            match.replace(self.ent_replace.get_text(), self.controller.main_controller)

    def _unhighlight_previous_matches(self):
        if not getattr(self, '_prev_unitview', ''):
            return

        for textview in self._prev_unitview.sources + self._prev_unitview.targets:
            buff = textview.get_buffer()
            buff.remove_all_tags(buff.get_start_iter(), buff.get_end_iter())


    # EVENT HANDLERS #
    def _on_entry_activate(self, entry):
        self.update_search()

    def _on_cursor_changed(self, cursor):
        assert cursor is self.storecursor

        unitcont = self.controller.main_controller.unit_controller
        if self._unit_modified_id:
            unitcont.disconnect(self._unit_modified_id)
        self._unit_modified_id = unitcont.connect('unit-modified', self._on_unit_modified)
        self._highlight_matches()

    def _on_replace_clicked(self, btn):
        if not self.storecursor or not self.ent_search.get_text() or not self.ent_replace.get_text():
            return
        self.update_search()

        if self.chk_replace_all.get_active():
            self._replace_all()
        else:
            current_unit = self.storecursor.model[self.storecursor.index]
            # Find matches in the current unit.
            unit_matches = [match for match in self.matches if match.unit is current_unit and match.part == 'target']
            if len(unit_matches) > 0:
                unit_matches[0].replace(self.ent_replace.get_text(), self.controller.main_controller)
                self.controller.main_controller.undo_controller.undo_stack.pop()
                self.controller.main_controller.undo_controller.undo_stack.undo_stack.pop()
                self.matches.remove(unit_matches[0])
            else:
                self.storecursor.move(1)

        self.update_search()

    def _on_search_clicked(self, btn):
        self._move_match(1)

    def _on_search_next(self, *args):
        self._move_match(1)

    def _on_search_prev(self, *args):
        self._move_match(-1)

    def _on_search_text_changed(self, entry):
        if self._search_timeout:
            gobject.source_remove(self._search_timeout)
            self._search_timeout = 0

        self._search_timeout = gobject.timeout_add(self.SEARCH_DELAY, self.update_search)

    def _on_start_search(self, _accel_group, _acceleratable, _keyval, _modifier):
        """This is called via the accelerator."""
        self.controller.select_mode(self)

    def _on_unit_modified(self, unit_controller, current_unit):
        unit_matches = self._get_matches_for_unit(current_unit)
        for match in unit_matches:
            if not self.re_search.match(match.get_getter()()[match.start:match.end]):
                logging.debug('Match to remove: %s' % (match))
                self.matches.remove(match)
                self.matchcursor.indices = range(len(self.matches))

    def _refresh_proxy(self, *args):
        self.update_search()
