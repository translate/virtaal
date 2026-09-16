#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from virtaal.common import pan_app


class Configurable:
    """Mixin providing load_config()/save_config() against one shared
    per-category ini file (CONFIG_FILENAME), keyed by the object's
    internal_name - replaces the identical pair reimplemented by hand
    in BasePlugin, BaseTerminologyModel and BaseTMModel."""

    CONFIG_FILENAME = None
    default_config = {}

    def load_config(self):
        self.config = {}
        self.config.update(self.default_config)
        config_file = os.path.join(pan_app.get_config_dir(), self.CONFIG_FILENAME)
        self.config.update(pan_app.load_config(config_file, self.internal_name))

    def save_config(self):
        config_file = os.path.join(pan_app.get_config_dir(), self.CONFIG_FILENAME)
        pan_app.save_config(config_file, self.config, self.internal_name)
