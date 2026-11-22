#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The token the local TM server (tmserver.py) and its client
(tmclient.py) share, without either importing the other."""

import secrets

#: The header every request carries the server's token in.
TOKEN_HEADER = "X-Virtaal-TM-Token"
#: The environment variable the server reads its token from: not a
#: command-line option, which other users can see.
TOKEN_ENV = "VIRTAAL_TMSERVER_TOKEN"


def new_token() -> str:
    return secrets.token_urlsafe(32)
