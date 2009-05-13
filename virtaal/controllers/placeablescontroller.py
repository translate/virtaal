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
import logging
from translate.storage.placeables import general, parse as parse_placeables, StringElem

from virtaal.common import pan_app, GObjectWrapper
from virtaal.views import placeablesguiinfo

from basecontroller import BaseController


class PlaceablesController(BaseController):
    """Basic controller for placeable-related logic."""

    __gtype_name__ = 'PlaceablesController'
    __gsignals__ = {
        'parsers-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, tuple()),
    }

    parsers = []
    """The list of parsers that should be used by the main placeables C{parse()}
    function.
    @see translate.storage.placeables.parse"""

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.placeables_controller = self
        self._init_parsers()
        self._init_parser_descriptions()
        self._init_notarget_list()

        self.main_controller.connect('quit', self._on_quit)

    def _init_notarget_list(self):
        self.non_target_placeables = [
            general.AltAttrPlaceable,
            general.EmailPlaceable,
            general.FilePlaceable,
            general.PunctuationPlaceable,
            general.UrlPlaceable,
        ]

    def _init_parsers(self):
        disabled = [name for name, state in pan_app.settings.placeable_state.items() if state.lower() == 'disabled']

        self.parsers = []
        for parser in general.parsers:
            classname = parser.im_self.__name__.lower()
            if classname in disabled:
                continue
            self.parsers.append(parser)

    def _init_parser_descriptions(self):
        self.parser_info = {}

        # Test for presence of parser classes by hand
        self.parser_info[general.AltAttrPlaceable.parse] = (
            _('"alt" attribute placeable'),
            _('Placeable for alt="..." tags (as found in HTML).')
        )
        self.parser_info[general.EmailPlaceable.parse] = (
            _('E-mail'),
            _('E-mail addresses are recognised as placeables.')
        )
        self.parser_info[general.FilePlaceable.parse] = (
            _('File location'),
            _('Handle file locations as placeables.')
        )
        self.parser_info[general.FormattingPlaceable.parse] = (
            _('C printf variables'),
            _('Placeable matching C printf-style variable formatting.')
        )
        self.parser_info[general.PunctuationPlaceable.parse] = (
            _('Punctuation'),
            _('Specifically for being able to copy non-standard punctuation easily.')
        )
        self.parser_info[general.UrlPlaceable.parse] = (
            _('URL'),
            _('Handle URLs as placeables.')
        )
        self.parser_info[general.XMLEntityPlaceable.parse] = (
            _('XML Entities'),
            _('Recognizes XML entities (such as &amp;foo;) as (constant) placeables.')
        )
        self.parser_info[general.XMLTagPlaceable.parse] = (
            _('XML Tags'),
            _('Handles XML tags as placeables.')
        )


    # METHODS #
    def add_parsers(self, *newparsers):
        """Add the specified parsers to the list of placeables parser functions."""
        if [f for f in newparsers if not callable(f)]:
            raise TypeError('newparsers may only contain callable objects.')

        self.parsers.extend(newparsers)
        self.emit('parsers-changed')

    def apply_parsers(self, elems, parsers=None):
        """Apply all selected placeable parsers to the list of string elements
            given.

            @param elems: The list of C{StringElem}s to apply the parsers to."""
        if not isinstance(elems, list) and isinstance(elems, StringElem):
            elems = [elems]

        if parsers is None:
            parsers = self.parsers

        for elem in elems:
            leaves = elem.flatten()
            for leaf in leaves:
                parsed = parse_placeables(leaf, parsers)
                if isinstance(leaf, (str, unicode)) and parsed != StringElem(leaf):
                    parent = elem.get_parent_elem(leaf)
                    if parent is not None:
                        parent.sub[parent.sub.index(leaf)] = StringElem(parsed)
        return elems

    def get_gui_info(self, placeable):
        """Get an appropriate C{StringElemGUI} or sub-class instance based on
        the type of C{placeable}. The mapping between placeables classes and
        GUI info classes is defined in
        L{virtaal.views.placeablesguiinfo.element_gui_map}."""
        if not isinstance(placeable, StringElem):
            raise ValueError('placeable must be a StringElem.')
        for plac_type, info_type in placeablesguiinfo.element_gui_map:
            if isinstance(placeable, plac_type):
                return info_type
        return placeablesguiinfo.StringElemGUI

    def remove_parsers(self, *parsers):
        changed = False
        for p in parsers:
            if p in self.parsers:
                self.parsers.remove(p)
                changed = True
        if changed:
            self.emit('parsers-changed')


    # EVENT HANDLERS #
    def _on_quit(self, main_ctrlr):
        for parser in general.parsers:
            classname = parser.im_self.__name__
            enabled = parser in self.parsers
            if classname in pan_app.settings.placeable_state or not enabled:
                pan_app.settings.placeable_state[classname] = enabled and 'enabled' or 'disabled'
