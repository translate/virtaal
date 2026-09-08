#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


class BaseLookupModel:
    """The base interface to be implemented by all look-up backend models."""

    description = ""
    """A description of the backend. This will be displayed to users."""
    display_name = None
    """The backend's name, suitable for display."""

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        """Initialise the model."""
        raise NotImplementedError()


    # METHODS #
    def create_menu_items(self, query, role, srclang, tgtlang):
        """Create the a list C{Gtk.MenuItem}s for the given parameters.

        @type  query: str
        @param query: The string to use in the look-up.
        @type  query_is_src: bool
        @param query_is_src: C{True} if C{query} is from a source text box. C{False} otherwise.
        @type  srclang: str
        @param srclang: The language code of the source language.
        @type  tgtlang: str
        @param tgtlang: The language code of the target language."""
        raise NotImplementedError()

    def destroy(self):
        pass
