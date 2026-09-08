#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .selectdialog import SelectDialog


class TestSelectDialog:
    """
    Test runner for SelectDialog.
    """

    def __init__(self):
        self.items = (
            {'enabled': True,  'name': 'item1', 'desc': 'desc1'},
            {'enabled': False, 'name': 'item2'                 },
            {'enabled': True,                   'desc': 'desc3'},
            {                  'name': 'item4', 'desc': 'desc4'},
            {'enabled': True,  'name': 'item5', 'desc': ''     },
            {'enabled': False, 'name': '',      'desc': 'desc6'},
        )
        self.dialog = SelectDialog(self.items, title='Test runner', message='Select the items you want:')
        self.dialog.connect('item-enabled',   self._on_dialog_action, 'Enabled')
        self.dialog.connect('item-disabled',  self._on_dialog_action, 'Disabled')
        self.dialog.connect('item-selected',  self._on_dialog_action, 'Selected')
        self.dialog.connect('selection-done', self._on_dialog_action, 'Selection done')

    def run(self):
        self.dialog.run()

    def _on_dialog_action(self, dialog, item, action):
        print('%s: %s' % (action, item))


if __name__ == '__main__':
    runner = TestSelectDialog()
    runner.run()
