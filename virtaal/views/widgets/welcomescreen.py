#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import gtk
from gobject import SIGNAL_RUN_FIRST

from virtaal.views.theme import current_theme

class WelcomeScreen(gtk.ScrolledWindow):
    """
    The scrolled window that contains the welcome screen container widget.
    """

    __gtype_name__ = 'WelcomeScreen'
    __gsignals__ = { 'button-clicked': (SIGNAL_RUN_FIRST, None, (str,)) }


    # INITIALISERS #
    def __init__(self, gui):
        """Constructor.
            @type  gui: C{gtk.Builder}
            @param gui: The GtkBuilder XML object to retrieve the welcome screen from."""
        super(WelcomeScreen, self).__init__()

        self.gui = gui

        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        win = gui.get_object('WelcomeScreen')
        if not win:
            raise ValueError('Welcome screen not found in GtkBuikder object.')
        child = win.child
        win.remove(child)
        self.add_with_viewport(child)

        self._get_widgets()
        self._init_feature_view()

    def _get_widgets(self):
        self.widgets = {}
        widget_names = ('img_banner', 'exp_features', 'txt_features')
        for wname in widget_names:
            self.widgets[wname] = self.gui.get_object(wname)

        self.widgets['buttons'] = {}
        button_names = (
            'open', 'recent1', 'recent2', 'recent3', 'recent4', 'recent5',
            'tutorial', 'cheatsheet', 'features_more', 'manual', 'locguide',
            'feedback'
        )
        for bname in button_names:
            btn = self.gui.get_object('btn_' + bname)
            self.widgets['buttons'][bname] = btn
            btn.connect('clicked', self._on_button_clicked, bname)


    def _style_widgets(self):
        url_fg_color = gtk.gdk.color_parse(current_theme['url_fg'])

        for s in [gtk.STATE_ACTIVE, gtk.STATE_NORMAL, gtk.STATE_SELECTED]:
            self.widgets['exp_features'].get_children()[1].modify_fg(s, url_fg_color)

        # Find a gtk.Label as a child of the button...
        for btn in self.widgets['buttons'].values():
            label = None
            if isinstance(btn.child, gtk.Label):
                label = btn.child
            else:
                for widget in btn.child.get_children():
                    if isinstance(widget, gtk.Label):
                        label = widget
                        break
            if label:
                for s in [gtk.STATE_ACTIVE, gtk.STATE_NORMAL, gtk.STATE_SELECTED]:
                    label.modify_fg(s, url_fg_color)

    def _init_feature_view(self):
        features = u"\n".join([
            u" • " + _("Translation memory"),
            u" • " + _("Terminology assistance"),
            u" • " + _("Quality checks"),
            u" • " + _("Machine translation"),
            u" • " + _("Highlighting and insertion of placeables"),
            u" • " + _("Many plugins and options for customization"),
        ])
        self.widgets['txt_features'].get_buffer().set_text(features)


    # METHODS #
    def set_banner_image(self, filename):
        self.widgets['img_banner'].set_from_file(filename)


    # SIGNAL HANDLERS #
    def _on_button_clicked(self, button, name):
        self.emit('button-clicked', name)

    def do_style_set(self, previous_style):
        self.child.modify_bg(gtk.STATE_NORMAL, self.style.base[gtk.STATE_NORMAL])
        self._style_widgets()
