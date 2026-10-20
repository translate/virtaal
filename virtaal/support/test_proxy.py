#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sys

import pytest
from gi.repository import Gio, GLib

from virtaal.support import httpclient, proxy

URL = 'http://virtaal.invalid/page'


@pytest.fixture
def linux(monkeypatch):
    for name in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
                 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(proxy, 'uses_desktop_proxy', lambda: True)


def _resolve_to(monkeypatch, *proxies, error=None):
    class Resolver:
        def lookup(self, url, cancellable):
            if error:
                raise error
            return list(proxies)
    monkeypatch.setattr(Gio.ProxyResolver, 'get_default', staticmethod(Resolver))


def test_desktop_proxy_returns_the_desktops_proxy(linux, monkeypatch):
    _resolve_to(monkeypatch, 'http://proxy.example:3128', 'direct://')
    assert proxy.desktop_proxy(URL) == 'http://proxy.example:3128'


def test_desktop_proxy_returns_an_empty_proxy_for_a_direct_connection(linux, monkeypatch):
    _resolve_to(monkeypatch, 'direct://')
    assert proxy.desktop_proxy(URL) == ''


def test_desktop_proxy_leaves_a_failed_lookup_to_the_environment(linux, monkeypatch):
    _resolve_to(monkeypatch, error=GLib.Error('no portal'))
    assert proxy.desktop_proxy(URL) is None


def test_desktop_proxy_leaves_it_to_the_environment_without_pygobject(linux, monkeypatch):
    # #4486: the asset manifest job runs the download helpers without it.
    monkeypatch.setitem(sys.modules, 'gi.repository', None)

    assert proxy.desktop_proxy(URL) is None

def test_desktop_proxy_leaves_proxy_environment_variables_in_charge(linux, monkeypatch):
    monkeypatch.setenv('http_proxy', 'http://env.example:8080')
    _resolve_to(monkeypatch, 'http://proxy.example:3128')
    assert proxy.desktop_proxy(URL) is None


@pytest.mark.parametrize('url', ['http://localhost:55555/tm', 'http://127.0.0.1:55555/tm', 'http://[::1]:55555/tm'])
def test_desktop_proxy_connects_directly_to_the_local_tm_server(linux, monkeypatch, url):
    _resolve_to(monkeypatch, 'http://proxy.example:3128')
    assert proxy.desktop_proxy(url) == ''


def _opened_with(monkeypatch):
    """The ProxyHandler proxies urlopen() opens with, or None for plain
        urllib.request.urlopen()."""
    opened = []
    monkeypatch.setattr(proxy.urllib.request, 'urlopen', lambda url, timeout: opened.append(None))

    class Opener:
        def __init__(self, handler):
            self.handler = handler

        def open(self, url, timeout):
            opened.append(self.handler.proxies)
    monkeypatch.setattr(proxy.urllib.request, 'build_opener', Opener)
    proxy.urlopen(URL, timeout=5)
    return opened[0]


def test_urlopen_goes_through_the_desktops_proxy_on_linux(linux, monkeypatch):
    _resolve_to(monkeypatch, 'http://proxy.example:3128')
    assert _opened_with(monkeypatch) == {'http': 'http://proxy.example:3128'}


def test_urlopen_connects_directly_when_the_desktop_has_no_proxy(linux, monkeypatch):
    _resolve_to(monkeypatch, 'direct://')
    assert _opened_with(monkeypatch) == {}


def test_urlopen_leaves_a_socks_proxy_to_urllib(linux, monkeypatch):
    _resolve_to(monkeypatch, 'socks5://proxy.example:1080')
    assert _opened_with(monkeypatch) is None


class _RecordingCurl:
    def __init__(self):
        self.opts = {}

    def setopt(self, opt, value):
        self.opts[opt] = value

    def getinfo(self, opt):
        return None


def test_httprequest_uses_the_desktops_proxy_on_linux(linux, monkeypatch):
    monkeypatch.setattr(httpclient.pycurl, 'Curl', _RecordingCurl)
    _resolve_to(monkeypatch, 'http://proxy.example:3128')

    request = httpclient.HTTPRequest(URL)

    assert request.curl.opts[httpclient.pycurl.PROXY] == 'http://proxy.example:3128'


def test_urlopen_ignores_the_resolver_on_windows_and_macos(monkeypatch):
    monkeypatch.setattr(proxy, 'uses_desktop_proxy', lambda: False)
    _resolve_to(monkeypatch, error=AssertionError('resolver asked'))
    opened = []
    monkeypatch.setattr(proxy.urllib.request, 'urlopen', lambda url, timeout: opened.append(url))

    proxy.urlopen(URL, timeout=5)

    assert opened == [URL]


def test_httprequest_ignores_the_resolver_on_windows_and_macos(monkeypatch):
    monkeypatch.setattr(proxy, 'uses_desktop_proxy', lambda: False)
    monkeypatch.setattr(httpclient.pycurl, 'Curl', _RecordingCurl)
    _resolve_to(monkeypatch, error=AssertionError('resolver asked'))

    request = httpclient.HTTPRequest(URL)

    assert httpclient.pycurl.PROXY not in request.curl.opts


@pytest.mark.parametrize('os_name, sys_platform, expected', [
    ('posix', 'linux', True),
    ('posix', 'freebsd14', True),
    ('posix', 'darwin', False),
    ('nt', 'win32', False),
])
def test_uses_desktop_proxy_everywhere_but_windows_and_macos(monkeypatch, os_name, sys_platform, expected):
    monkeypatch.setattr(proxy.os, 'name', os_name)
    monkeypatch.setattr(proxy.sys, 'platform', sys_platform)
    assert proxy.uses_desktop_proxy() is expected
