#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Manual, interactive demo for SelectView - opens a real window for a
human to eyeball, not an automated test. Run directly:
python demo_selectview.py
(Renamed from test_selectview.py, which pytest was picking up by
filename convention alone despite having no assertions.)"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .selectview import SelectView


class SelectViewTestWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.connect('destroy', lambda *args: Gtk.main_quit())
        self.add(self.create_selectview())

    def create_selectview(self):
        self.items = (
            {'enabled': True,  'name': 'item1', 'desc': 'desc1'},
            {'enabled': False, 'name': 'item2'                 },
            {'enabled': True,                   'desc': 'desc3'},
            {                  'name': 'item4', 'desc': 'desc4'},
            {'enabled': True,  'name': 'item5', 'desc': ''     },
            {'enabled': False, 'name': '',      'desc': 'desc6'},
        )
        self.selectview = SelectView(self.items)
        self.selectview.connect('item-enabled', self._on_item_action, 'enabled')
        self.selectview.connect('item-disabled', self._on_item_action, 'disabled')
        self.selectview.connect('item-selected', self._on_item_action, 'selected')
        return self.selectview


    def _on_item_action(self, sender, item_info, action):
        print('Item %s: %s' % (action, item_info))


if __name__ == '__main__':
    win = SelectViewTestWindow()
    win.show_all()
    Gtk.main()
