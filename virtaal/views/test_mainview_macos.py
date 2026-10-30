#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""MainView's AppKit calls, run against real native windows and menus
and read back from AppKit."""

import ctypes
import logging
import sys
from unittest import mock

import gi
import pytest
from gi.repository import Gtk

from virtaal.views import mainview
from virtaal.views.mainview import _objc_class, _objc_send

macos_only = pytest.mark.skipif(sys.platform != 'darwin', reason='AppKit is macOS-only')


def _nsstring(text):
    return _objc_send(_objc_class('NSString'), 'stringWithUTF8String:',
                      text.encode(), argtypes=[ctypes.c_char_p])


def _text(nsstring):
    return _objc_send(nsstring, 'UTF8String', restype=ctypes.c_char_p).decode()


def _menu(title, *items):
    """A native menu holding C{items}: titles, or (title, submenu) pairs."""
    menu = _objc_send(_objc_send(_objc_class('NSMenu'), 'alloc'), 'initWithTitle:', _nsstring(title))
    for item in items:
        name, submenu = item if isinstance(item, tuple) else (item, None)
        menuitem = _objc_send(menu, 'addItemWithTitle:action:keyEquivalent:',
                              _nsstring(name), None, _nsstring(''))
        if submenu:
            _objc_send(menuitem, 'setSubmenu:', submenu, restype=None)
    return menu


@pytest.fixture
def main_menu():
    """Install a native main menu for the test, then put back the old one."""
    nsapp = _objc_send(_objc_class('NSApplication'), 'sharedApplication')
    old = _objc_send(nsapp, 'mainMenu')

    def install(menu):
        _objc_send(nsapp, 'setMainMenu:', menu, restype=None)
        return menu
    yield install
    _objc_send(nsapp, 'setMainMenu:', old, restype=None)


def _nswindow(window):
    libgdk = ctypes.CDLL(None)
    libgdk.gdk_quartz_window_get_nswindow.restype = ctypes.c_void_p
    libgdk.gdk_quartz_window_get_nswindow.argtypes = [ctypes.c_void_p]
    return libgdk.gdk_quartz_window_get_nswindow(ctypes.c_void_p(hash(window.get_window())))


@macos_only
def test_set_document_edited_marks_the_native_window():
    window = Gtk.Window()
    window.realize()
    nswindow = _nswindow(window)
    assert nswindow
    try:
        mainview._set_document_edited(window.get_window(), True)
        assert _objc_send(nswindow, 'isDocumentEdited', restype=ctypes.c_bool)

        mainview._set_document_edited(window.get_window(), False)
        assert not _objc_send(nswindow, 'isDocumentEdited', restype=ctypes.c_bool)
    finally:
        window.destroy()


@macos_only
def test_find_native_menu_item_finds_an_item_in_a_submenu():
    menu = _menu('', ('File', _menu('File', 'Open', ('Recent', _menu('Recent', 'a.po')))),
                 ('Navigation', _menu('Navigation', 'Next')))

    item = mainview._find_native_menu_item(menu, 'a.po')

    assert item
    assert _text(_objc_send(item, 'title')) == 'a.po'
    assert _text(_objc_send(mainview._find_native_menu_item(menu, 'Next'), 'title')) == 'Next'


@macos_only
def test_find_native_menu_item_returns_none_for_a_missing_title():
    menu = _menu('', ('File', _menu('File', 'Open')))

    assert mainview._find_native_menu_item(menu, 'Close') is None


@macos_only
def test_set_native_return_key_shows_return_with_its_modifiers(main_menu):
    menu = main_menu(_menu('', ('Navigation', _menu('Navigation', 'Next Unit', 'Previous Unit'))))
    modifiers = mainview.NS_CONTROL_KEY_MASK | mainview.NS_SHIFT_KEY_MASK

    mainview._set_native_return_key('Previous Unit', modifiers)

    item = mainview._find_native_menu_item(menu, 'Previous Unit')
    assert _text(_objc_send(item, 'keyEquivalent')) == '\r'
    assert _objc_send(item, 'keyEquivalentModifierMask', restype=ctypes.c_ulong) == modifiers
    other = mainview._find_native_menu_item(menu, 'Next Unit')
    assert _text(_objc_send(other, 'keyEquivalent')) == ''


@macos_only
def test_set_native_return_key_without_the_item_changes_nothing(main_menu):
    menu = main_menu(_menu('', ('Navigation', _menu('Navigation', 'Next Unit'))))

    mainview._set_native_return_key('Previous Unit', mainview.NS_CONTROL_KEY_MASK)

    item = mainview._find_native_menu_item(menu, 'Next Unit')
    assert _text(_objc_send(item, 'keyEquivalent')) == ''


@macos_only
def test_set_native_return_key_without_a_main_menu_does_nothing(main_menu):
    main_menu(None)

    mainview._set_native_return_key('Next Unit', mainview.NS_CONTROL_KEY_MASK)


def test_macos_integration_without_gtk_mac_integration_leaves_the_menu_bar(monkeypatch, caplog):
    # A source install without gtk-mac-integration.
    real_require_version = gi.require_version

    def require_version(namespace, version):
        if namespace == 'GtkosxApplication':
            raise ValueError('Namespace GtkosxApplication not available')
        return real_require_version(namespace, version)
    monkeypatch.setattr(gi, 'require_version', require_version)
    monkeypatch.setattr(mainview, '_disable_window_tabbing', lambda: None)
    view = mock.Mock()

    with caplog.at_level(logging.DEBUG):
        mainview.MainView._setup_macos_integration(view)

    assert not view.menubar.hide.called
    assert 'GtkosxApplication not found' in caplog.text
