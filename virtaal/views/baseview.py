#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository.Gtk import Builder

from virtaal.common import pan_app

#cache builders so that we don't parse files repeatedly
_builders = {}


class BaseView:
    """Interface for views."""

    def __init__(self):
        raise NotImplementedError('This interface cannot be instantiated.')

    @classmethod
    def load_builder_file(cls, path_parts, root=None, domain=''):
        _id = "/".join(path_parts)
        if _id in _builders:
            return _builders[_id]
        buildername = pan_app.get_abs_data_filename(path_parts)
        builder = Builder()
        builder.add_from_file(buildername)
        builder.set_translation_domain(domain)
        _builders[_id] = builder
        return builder

    def show(self):
        raise NotImplementedError('This method needs to be implemented by all sub-classes.')
