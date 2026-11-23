#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.macmenu import menu_title, strip_bracket_mnemonics


@pytest.mark.parametrize('label, title', [
    ('파일(_F)', '파일'),                                     # po/ko.po
    ('ファイル(_F)', 'ファイル'),                              # po/ja.po
    ('文件(_F)', '文件'),                                      # po/zh_CN.po
    ('누락된 언어 추가(_A)…', '누락된 언어 추가…'),              # po/ko.po
    ('添加缺少的语言(_A)...', '添加缺少的语言...'),              # po/zh_CN.po
    ('অনুপস্থিত ভাষা যোগ করুন…(_A)', 'অনুপস্থিত ভাষা যোগ করুন…'),  # po/bn_IN.po
    ('ফাইল (_F)', 'ফাইল'),                                     # po/bn_IN.po
    ('术语文件(_F)：', '术语文件：'),                           # po/zh_CN.po
    ('文件（_F）', '文件'),
    ('開く(_O)', '開く'),                                      # GTK's ja stock label
])
def test_menu_title_drops_a_bracketed_access_key(label, title):
    assert menu_title(label) == title


@pytest.mark.parametrize('label', [
    '_File',
    'R_edigera',
    'Properties (beta)',
    'Version (_2) of',
    'Copy (__F)',
    '原文(_S) — %(langname)s',
])
def test_menu_title_keeps_other_labels(label):
    assert menu_title(label) == label


def _menu_item(label, submenu_labels=()):
    item = Gtk.MenuItem.new_with_mnemonic(label)
    if submenu_labels:
        submenu = Gtk.Menu()
        for sub_label in submenu_labels:
            submenu.append(Gtk.MenuItem.new_with_mnemonic(sub_label))
        item.set_submenu(submenu)
    return item


def _titles(menu_shell):
    return [item.get_child().get_label() for item in menu_shell.get_children()]


def test_strip_bracket_mnemonics_covers_items_and_submenus():
    menubar = Gtk.MenuBar()
    menubar.append(_menu_item('파일(_F)', ['열기(_O)…', '_Save']))
    menubar.append(_menu_item('_Edit'))

    strip_bracket_mnemonics(menubar)

    assert _titles(menubar) == ['파일', '_Edit']
    assert _titles(menubar.get_children()[0].get_submenu()) == ['열기…', '_Save']


def test_strip_bracket_mnemonics_follows_later_changes():
    # Plug-ins and modes add items, and GTK resets stock labels, after
    # the menu bar moves to macOS.
    menubar = Gtk.MenuBar()
    file_item = _menu_item('파일(_F)')
    menubar.append(file_item)
    strip_bracket_mnemonics(menubar)

    file_item.set_label('ファイル(_F)')
    menubar.append(_menu_item('도구(_T)'))
    file_item.set_submenu(Gtk.Menu())
    file_item.get_submenu().append(_menu_item('최근 파일(_R)'))

    assert _titles(menubar) == ['ファイル', '도구']
    assert _titles(file_item.get_submenu()) == ['최근 파일']


def test_strip_bracket_mnemonics_leaves_labels_without_access_keys():
    # A recent file's name is shown as is.
    menubar = Gtk.MenuBar()
    menubar.append(Gtk.MenuItem(label='notes(_F)'))

    strip_bracket_mnemonics(menubar)

    assert _titles(menubar) == ['notes(_F)']
