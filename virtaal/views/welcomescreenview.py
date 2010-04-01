#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import gtk

from virtaal.common.pan_app import get_abs_data_filename
from virtaal.views.widgets.welcomescreen import WelcomeScreen

from baseview import BaseView


class WelcomeScreenView(BaseView):
    """Manages the welcome screen widget."""

    PARENT_VBOX_POSITION = 2
    """Index of the welcome screen in the main VBox."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        gladefile, gui = self.load_glade_file(["virtaal", "virtaal.glade"], root='WelcomeScreen', domain="virtaal")
        self.widget = WelcomeScreen(gui)
        self.parent_widget = self.controller.main_controller.view.gui.get_widget('vbox_main')

        self.set_widget_bg()
        self.widget.set_banner_image(get_abs_data_filename(['virtaal', 'welcome_screen_banner.png']))
        self.widget.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.widget.connect('button-clicked', self._on_button_clicked)

    def set_widget_bg(self):
        import gtk
        from gobject import idle_add
        idle_add(lambda: self.widget.child.modify_bg(gtk.STATE_NORMAL, self.widget.style.base[gtk.STATE_NORMAL]))


    # METHODS #
    def hide(self):
        self.parent_widget.remove(self.widget)

    def show(self):
        if not self.widget.parent:
            self.parent_widget.add(self.widget)
        else:
            self.widget.reparent(self.parent_widget)
        self.parent_widget.child_set_property(self.widget, 'position', self.PARENT_VBOX_POSITION)
        self.parent_widget.child_set_property(self.widget, 'expand', True)

        self.widget.show()

    def update_recent_buttons(self, items):
        buttons = [
            self.widget.widgets['buttons']['recent' + str(i)] for i in range(1, self.controller.MAX_RECENT+1)
        ]
        markup = '<span foreground="blue" underline="single">%(name)s</span>'

        for i in range(len(items)):
            buttons[i].child.get_children()[0].set_from_file(get_abs_data_filename(['icons', 'x-translation_24.png']))
            buttons[i].child.get_children()[1].set_markup(markup % {'name': items[i]['name']})
            buttons[i].props.visible = True
        for i in range(len(items), 5):
            buttons[i].props.visible = False


    # EVENT HANDLERS #
    def _on_button_clicked(self, button, name):
        """This method basically delegates button clicks to controller actions."""
        if name == 'open':
            self.controller.open_file()
        elif name.startswith('recent'):
            n = int(name[len('recent'):])
            self.controller.open_recent(n)
        elif name == 'tutorial':
            self.controller.open_tutorial()
        elif name == 'cheatsheet':
            self.controller.open_cheatsheat()
        else:
            self.controller.try_open_link(name)
