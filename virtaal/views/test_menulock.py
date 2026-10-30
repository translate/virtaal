#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.menulock import MenuLock


def _menus():
    """File > Open, Save (greyed), a separator, Recent > a.po; Edit > Paste."""
    bar = Gtk.MenuBar()
    items = {}
    for top, children in (('File', ('Open', 'Save', None, 'Recent')), ('Edit', ('Paste',))):
        menu_item = Gtk.MenuItem(label=top)
        menu = Gtk.Menu()
        for name in children:
            item = Gtk.SeparatorMenuItem() if name is None else Gtk.MenuItem(label=name)
            menu.append(item)
            if name:
                items[name] = item
        menu_item.set_submenu(menu)
        bar.append(menu_item)
        items[top] = menu_item
    recent = Gtk.Menu()
    items['a.po'] = Gtk.MenuItem(label='a.po')
    recent.append(items['a.po'])
    items['Recent'].set_submenu(recent)
    items['Save'].set_sensitive(False)
    return bar, items


def _sensitive(items):
    return {name: item.get_sensitive() for name, item in items.items()}


def test_lock_greys_out_menu_items_but_the_kept_ones_and_the_menus():
    # #4611: on macOS the menu bar stays live while a dialog has the focus.
    bar, items = _menus()
    lock = MenuLock(lambda: bar, keep=[items['Paste']])

    lock.lock()

    assert _sensitive(items) == {'File': True, 'Open': False, 'Save': False, 'Recent': True,
                                 'a.po': False, 'Edit': True, 'Paste': True}
    assert lock.locked


def test_unlock_puts_every_item_back_as_it_was():
    bar, items = _menus()
    before = _sensitive(items)
    lock = MenuLock(lambda: bar)

    lock.lock()
    lock.unlock()

    assert _sensitive(items) == before
    assert not lock.locked


def test_a_change_while_locked_is_kept_for_unlock():
    bar, items = _menus()
    lock = MenuLock(lambda: bar)
    lock.lock()

    items['Save'].set_sensitive(True)   # e.g. the file was modified
    items['Open'].set_sensitive(False)

    assert not items['Save'].get_sensitive()
    lock.unlock()
    assert items['Save'].get_sensitive()
    assert not items['Open'].get_sensitive()


def test_locking_twice_keeps_the_first_state():
    bar, items = _menus()
    lock = MenuLock(lambda: bar)

    lock.lock()
    lock.lock()
    lock.unlock()

    assert items['Open'].get_sensitive()


def test_unlock_without_lock_changes_nothing():
    bar, items = _menus()
    before = _sensitive(items)

    MenuLock(lambda: bar).unlock()

    assert _sensitive(items) == before
