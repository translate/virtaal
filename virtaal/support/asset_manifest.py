#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""A single cached manifest of every downloadable asset Virtaal knows
about (spell-check dictionaries, autocorrect data, thesauruses - see
devsupport/testing/generate_asset_manifest.py, which builds the real
one from LibreOffice's own repos), so a caller can ask "does locale X
have resource Y, and is what I have installed still current" as a pure
local lookup instead of live network discovery.

Fetched once ever on first use, refreshed only every _REFRESH_DAYS
after that - not on every cold start, and not per language switch.
Callers that get None back (never fetched successfully at all) should
fall back to their own live-discovery code, kept unchanged elsewhere
for exactly this case.
"""

import logging
import os
import time
from datetime import date

import yaml
from gi.repository import Gdk, GLib, Gtk

from virtaal.support.dictionary_source import candidate_folders

MANIFEST_URL = 'https://raw.githubusercontent.com/translate/virtaal/asset-manifest/asset-manifest.yaml'
_CACHE_FILENAME = 'asset-manifest.yaml'
_REFRESH_DAYS = 7


def installed_asset_key(resource_type, locale_code):
    """The pan_app.settings.installed_assets key for one
    (resource_type, locale) pair - configparser lowercases keys and
    rejects ':' as a delimiter, so '.' plus a lowercased locale."""
    return '%s.%s' % (resource_type, locale_code.replace('-', '_').lower())


def entry_shas(entry):
    """Comma-joined file shas for one manifest entry - the value
    stored in/compared against pan_app.settings.installed_assets."""
    return ','.join(f['sha'] for f in entry['files'])


def _extract_etag(request):
    """request.result_headers is httpclient.py's own BytesIO - same
    parsing terminology/models/pontoon.py and autoterm.py already use
    for their own conditional-GET caching."""
    headers = request.result_headers.getvalue().splitlines()
    etagline = [line for line in headers if line.lower().startswith(b'etag:')]
    if not etagline:
        return ''
    return etagline[0][7:-1].decode('ascii', errors='replace')


# --- Idle-lull scheduling - shared by the manifest's own refresh and
#     any caller's actual asset download, so neither competes with the
#     GIL right as a user starts typing. Gdk.Event.handler_set() is the
#     one mechanism that sees every input event application-wide before
#     normal GTK dispatch, without changing how those events are
#     handled, as long as the installed handler still calls
#     Gtk.main_do_event() itself. ---

_last_activity = [time.monotonic()]
_activity_tracker_installed = [False]


def _ensure_activity_tracker_installed():
    if _activity_tracker_installed[0]:
        return
    _activity_tracker_installed[0] = True

    def _on_event(event):
        _last_activity[0] = time.monotonic()
        Gtk.main_do_event(event)

    Gdk.Event.handler_set(_on_event)


def schedule_after_idle_lull(callback, quiet_seconds=3, max_wait_seconds=30):
    """Calls callback() once input has been quiet for quiet_seconds,
    or after max_wait_seconds regardless (so a continuously-typing
    session doesn't starve it forever)."""
    _ensure_activity_tracker_installed()
    deadline = time.monotonic() + max_wait_seconds

    def _poll():
        now = time.monotonic()
        if now - _last_activity[0] >= quiet_seconds or now >= deadline:
            callback()
            return False
        return True

    GLib.timeout_add_seconds(1, _poll)


class AssetManifest:
    def __init__(self, client=None, config_dir=None, schedule_after_idle_lull=schedule_after_idle_lull):
        self._client = client
        self._schedule_after_idle_lull = schedule_after_idle_lull
        if config_dir is None:
            from virtaal.common import pan_app
            config_dir = pan_app.get_config_dir()
        self._cache_path = os.path.join(config_dir, _CACHE_FILENAME)
        self._data = None
        self._load_cached()

    def _load_cached(self):
        try:
            with open(self._cache_path, 'rb') as f:
                self._data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logging.debug('asset manifest: no usable cache (%s)', e)
            self._data = None

    def _last_fetched(self):
        from virtaal.common import pan_app
        value = pan_app.settings.general.get('assets_manifest_fetched')
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def ensure_fresh(self, on_done=None):
        """Fetches the manifest if it's never been fetched (promptly -
        nothing to interrupt on a fresh profile), or refreshes it (after
        an idle lull) if the last fetch is older than _REFRESH_DAYS.
        Otherwise a no-op - calls on_done() immediately if given."""
        on_done = on_done or (lambda: None)
        last_fetched = self._last_fetched()
        if last_fetched is None:
            self._fetch(on_done)
        elif (date.today() - last_fetched).days >= _REFRESH_DAYS:
            self._schedule_after_idle_lull(lambda: self._fetch(on_done))
        else:
            on_done()

    def _fetch(self, on_done):
        client = self._client
        if client is None:
            from virtaal.support.httpclient import HTTPClient
            client = HTTPClient()
            client.set_virtaal_useragent()
            self._client = client
        # Only send a conditional If-None-Match when self._data is
        # actually usable (a real cache to fall back on if the server
        # confirms nothing changed) - an unconditional GET is safer
        # than trusting a stored etag with nothing behind it (e.g. the
        # cache file went missing after a successful fetch recorded
        # its etag).
        etag = None
        if self._data is not None:
            from virtaal.common import pan_app
            etag = pan_app.settings.general.get('assets_manifest_etag') or None
        client.get(MANIFEST_URL, lambda request, result: self._on_fetched(request, result, on_done),
                    etag=etag, error_callback=lambda request, status: self._on_fetch_error(on_done))

    def _on_fetched(self, request, result, on_done):
        from virtaal.common import pan_app
        if request.status == 304:
            # Our own cached copy already matches - nothing to
            # re-parse or rewrite, just record that we checked.
            pan_app.settings.general['assets_manifest_fetched'] = date.today().isoformat()
            return on_done()
        try:
            data = yaml.safe_load(result.decode('utf-8')) or {}
        except (ValueError, UnicodeDecodeError, yaml.YAMLError) as e:
            logging.debug('asset manifest: bad response (%s)', e)
            return self._on_fetch_error(on_done)
        self._data = data
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f)
        except OSError as e:
            logging.debug('asset manifest: could not cache locally (%s)', e)
        pan_app.settings.general['assets_manifest_fetched'] = date.today().isoformat()
        pan_app.settings.general['assets_manifest_etag'] = _extract_etag(request)
        on_done()

    def _on_fetch_error(self, on_done):
        logging.debug('asset manifest: fetch failed')
        on_done()

    def get(self, resource_type, locale_code):
        """{folder, files: [{name, sha}, ...]} covering locale_code
        for resource_type, or None if the manifest was never
        successfully fetched, or has nothing for this locale."""
        if not self._data:
            return None
        entries = self._data.get(resource_type) or {}
        candidates = candidate_folders(locale_code, entries)
        if not candidates:
            return None
        return entries[candidates[0]]
