#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.
#
# Loosely descended from translate-toolkit's translate/services/tmserver.py
# (dropped upstream, no replacement, after release 3.18.1) - vendored at
# first, now rewritten on Bottle for routing and request/response
# handling in place of the vendored selector.py router and hand-rolled
# WSGI plumbing. Still served over cheroot, via Bottle's own server
# adapter.

"""
A translation memory server using tmdb for storage, communicates with
clients using JSON over HTTP.
"""

import json
import logging
import sys
from argparse import ArgumentParser
from io import BytesIO

from bottle import Bottle, request, response
from translate.storage import base, factory

from virtaal.support import tmdb

logger = logging.getLogger(__name__)


class TMServer:
    """A RESTful JSON TM server."""

    def __init__(
        self,
        tmdbfile,
        tmfiles,
        max_candidates=3,
        min_similarity=75,
        max_length=1000,
        prefix="",
        source_lang=None,
        target_lang=None,
    ) -> None:
        if not isinstance(tmdbfile, str):
            tmdbfile = tmdbfile.decode(sys.getfilesystemencoding())

        self.tmdb = tmdb.TMDB(tmdbfile, max_candidates, min_similarity, max_length)

        if tmfiles:
            self._load_files(tmfiles, source_lang, target_lang)

        # initialize url dispatcher
        self.rest = Bottle()
        unit_path = f"{prefix}/<slang>/<tlang>/unit/<uid:path>"
        store_path = f"{prefix}/<slang>/<tlang>/store/<sid:path>"
        self.rest.route(unit_path, "GET", self.translate_unit)
        self.rest.route(unit_path, "POST", self.update_unit)
        self.rest.route(unit_path, "PUT", self.add_unit)
        self.rest.route(unit_path, "DELETE", self._forget_unit_route)
        self.rest.route(store_path, "GET", self._get_store_stats_route)
        self.rest.route(store_path, "PUT", self.upload_store)
        self.rest.route(store_path, "POST", self.add_store)
        self.rest.route(store_path, "DELETE", self._forget_store_route)

    def _load_files(self, tmfiles, source_lang, target_lang) -> None:
        if isinstance(tmfiles, list):
            for tmfile in tmfiles:
                self.tmdb.add_store(factory.getobject(tmfile), source_lang, target_lang)
        elif tmfiles:
            self.tmdb.add_store(factory.getobject(tmfiles), source_lang, target_lang)

    def translate_unit(self, slang, tlang, uid):
        response.content_type = "text/plain"
        candidates = self.tmdb.translate_unit(uid, slang, tlang)
        logger.debug("candidates: %s", candidates)
        body = json.dumps(candidates, indent=4)
        callback = request.query.callback
        if callback:
            body = f"{callback}({body})"
        return body

    def add_unit(self, slang, tlang, uid):
        response.content_type = "text/plain"
        data = json.loads(request.body.read())
        unit = base.TranslationUnit(data["source"])
        unit.target = data["target"]
        self.tmdb.add_unit(unit, slang, tlang)
        return ""

    def update_unit(self, slang, tlang, uid):
        response.content_type = "text/plain"
        data = json.loads(request.body.read())
        unit = base.TranslationUnit(data["source"])
        unit.target = data["target"]
        self.tmdb.add_unit(unit, slang, tlang)
        return ""

    def forget_unit(self, uid):
        # FIXME: implement me
        response.content_type = "text/plain"
        return "FIXME"

    def _forget_unit_route(self, slang, tlang, uid):
        return self.forget_unit(uid)

    def get_store_stats(self, sid):
        # FIXME: implement me
        response.content_type = "text/plain"
        return "FIXME"

    def _get_store_stats_route(self, slang, tlang, sid):
        return self.get_store_stats(sid)

    def upload_store(self, slang, tlang, sid):
        """Add units from uploaded file to tmdb."""
        response.content_type = "text/plain"
        data = BytesIO(request.body.read())
        data.name = sid
        store = factory.getobject(data)  # ty:ignore[invalid-argument-type]
        count = self.tmdb.add_store(store, slang, tlang)
        return f"added {count} units from {sid}"

    def add_store(self, slang, tlang, sid):
        """Add unit from POST data to tmdb."""
        response.content_type = "text/plain"
        units = json.loads(request.body.read())
        count = self.tmdb.add_list(units, slang, tlang)
        return f"added {count} units from {sid}"

    def forget_store(self, sid):
        # FIXME: implement me
        response.content_type = "text/plain"
        return "FIXME"

    def _forget_store_route(self, slang, tlang, sid):
        return self.forget_store(sid)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-d",
        "--tmdb",
        dest="tmdbfile",
        default=":memory:",
        help="translation memory database file",
    )
    parser.add_argument(
        "-f",
        "--import-translation-file",
        dest="tmfiles",
        action="append",
        help="translation file to import into the database",
    )
    parser.add_argument(
        "-t",
        "--import-target-lang",
        dest="target_lang",
        help="target language of translation files",
    )
    parser.add_argument(
        "-s",
        "--import-source-lang",
        dest="source_lang",
        help="source language of translation files",
    )
    parser.add_argument(
        "-b",
        "--bind",
        dest="bind",
        default="localhost",
        help="address to bind server to (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=8888,
        help="port to listen on (default: %(default)s)",
    )
    parser.add_argument(
        "--max-candidates",
        dest="max_candidates",
        type=int,
        default=3,
        help="Maximum number of candidates",
    )
    parser.add_argument(
        "--min-similarity",
        dest="min_similarity",
        type=int,
        default=75,
        help="minimum similarity",
    )
    parser.add_argument(
        "--max-length",
        dest="max_length",
        type=int,
        default=1000,
        help="Maximum string length",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=False,
        help="enable debugging features",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    # setup debugging
    format = "%(asctime)s %(levelname)s %(message)s"
    level = logging.DEBUG if args.debug else logging.WARNING
    if args.debug:
        format = "%(levelname)7s %(module)s.%(funcName)s:%(lineno)d: %(message)s"

    logging.basicConfig(level=level, format=format)

    application = TMServer(
        args.tmdbfile,
        args.tmfiles,
        max_candidates=args.max_candidates,
        min_similarity=args.min_similarity,
        max_length=args.max_length,
        prefix="/tmserver",
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    logger.info("Starting server, listening on port %s", args.port)
    try:
        application.rest.run(
            host=args.bind, port=args.port, server="cheroot", quiet=not args.debug
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
