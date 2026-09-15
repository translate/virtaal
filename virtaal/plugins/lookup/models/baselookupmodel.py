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
    configure_func = None
    """A callable(parent_window) opening this model's own settings
    dialog, offered in the Select Look-up Services list - None (the
    default) if there's nothing to configure. weblookup.py is the
    only model that currently sets its own; every model needs this
    attribute to exist at all, not just the ones with something to
    configure - select_backends() reads it off every enabled model."""

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        """Initialise the model."""
        raise NotImplementedError()


    # METHODS #
    def create_menu_items(self, query, role, srclang, tgtlang, textbox):
        """Create the a list C{Gtk.MenuItem}s for the given parameters.

        @type  query: str
        @param query: The string to use in the look-up.
        @type  query_is_src: bool
        @param query_is_src: C{True} if C{query} is from a source text box. C{False} otherwise.
        @type  srclang: str
        @param srclang: The language code of the source language.
        @type  tgtlang: str
        @param tgtlang: The language code of the target language.
        @type  textbox: the source/target text box the selection came
            from - only needed by a model whose action edits that
            selection in place (e.g. inserting a chosen synonym)
            rather than just opening something external."""
        raise NotImplementedError()

    def destroy(self):
        pass
