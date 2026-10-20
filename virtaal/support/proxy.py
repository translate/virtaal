#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The desktop's proxy settings on Linux, where urllib only reads the
proxy environment variables. GLib's proxy resolver reads GNOME's and KDE's
settings, and asks the desktop portal inside a Flatpak."""

import ipaddress
import logging
import os
import sys
import urllib.request
from urllib import parse


def uses_desktop_proxy():
    """Windows and macOS: urllib already reads the system's settings."""
    return os.name != 'nt' and sys.platform != 'darwin'


def desktop_proxy(url):
    """The proxy for C{url}, '' for a direct connection, or C{None} when
        the proxy environment variables apply (set, or the lookup failed)."""
    if urllib.request.getproxies_environment():
        return None
    # The local TM server, even when the desktop lists no exceptions.
    if _is_loopback(parse.urlsplit(url).hostname):
        return ''
    try:
        from gi.repository import Gio, GLib
    except ImportError:
        # Without PyGObject: the asset manifest job (#4486).
        return None
    try:
        proxies = Gio.ProxyResolver.get_default().lookup(url, None)
    except GLib.Error as error:
        logging.warning('Proxy lookup for %s failed: %s', url, error.message)
        return None
    proxy = proxies[0] if proxies else 'direct://'
    return '' if proxy == 'direct://' else proxy


def _is_loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def urlopen(url, timeout):
    """C{urllib.request.urlopen()} through the desktop's proxy on Linux."""
    proxy = desktop_proxy(url) if uses_desktop_proxy() else None
    # urllib only speaks to HTTP proxies.
    if proxy is None or proxy and parse.urlsplit(proxy).scheme not in ('http', 'https'):
        return urllib.request.urlopen(url, timeout=timeout)
    proxies = {parse.urlsplit(url).scheme: proxy} if proxy else {}
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies)).open(url, timeout=timeout)
