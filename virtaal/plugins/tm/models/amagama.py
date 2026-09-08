#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from . import remotetm
from .basetmmodel import BaseTMModel


class TMModel(remotetm.TMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'AmagamaTMModel'
    display_name = _('Amagama')
    description = _('Previous translations for Free and Open Source Software')
    #l10n: Try to keep this as short as possible.
    shortname = _('Amagama')

    default_config = {
            "url": "https://amagama-live.translatehouse.org/api/v1/",
    }
    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        # Do not use super() here, as remotetm.TMModel does a bit more than we
        # want in this case.
        BaseTMModel.__init__(self, controller)
        self.internal_name = internal_name
        self.load_config()
        url = self.config["url"]

        from virtaal.support import tmclient
        self.tmclient = tmclient.TMClient(url)
        self.tmclient.set_virtaal_useragent()


    def push_store(self, store_controller):
        pass

    def upload_store(self, store_controller):
        pass
