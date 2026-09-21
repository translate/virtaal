#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GLib, GObject, Gtk

from virtaal.views import theme
from virtaal.views.theme import current_theme, set_widget_bg_color, set_widget_fg_color


class WelcomeScreen(Gtk.ScrolledWindow):
    """
    The scrolled window that contains the welcome screen container widget.
    """

    __gtype_name__ = 'WelcomeScreen'
    __gsignals__ = {'button-clicked': (GObject.SignalFlags.RUN_FIRST, None, (str,))}


    # INITIALISERS #
    def __init__(self, gui):
        """Constructor.
            @type  gui: C{Gtk.Builder}
            @param gui: The GtkBuilder XML object to retrieve the welcome screen from."""
        super().__init__()

        self.gui = gui
        self._child_fg_provider = None

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        win = gui.get_object('WelcomeScreen')
        if not win:
            raise ValueError('Welcome screen not found in GtkBuikder object.')
        child = win.get_child()
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
            'feedback', 'report_bug'
        )
        for bname in button_names:
            btn = self.gui.get_object('btn_' + bname)
            self.widgets['buttons'][bname] = btn
            btn.connect('clicked', self._on_button_clicked, bname)


    def _style_widgets(self):
        set_widget_fg_color(self.widgets['exp_features'].get_children()[1], current_theme['url_fg'])

        # Find a Gtk.Label as a child of the button...
        for btn in self.widgets['buttons'].values():
            label = None
            if isinstance(btn.get_child(), Gtk.Label):
                label = btn.get_child()
            else:
                for widget in btn.get_child().get_children():
                    if isinstance(widget, Gtk.Label):
                        label = widget
                        break
            if label:
                set_widget_fg_color(label, current_theme['url_fg'])

    def _init_feature_view(self):
        features = "\n".join([
            " • " + _("Translation memory"),
            " • " + _("Terminology assistance"),
            " • " + _("Quality checks"),
            " • " + _("Machine translation"),
            " • " + _("Highlighting and insertion of placeables"),
            " • " + _("Many plugins and options for customization"),
        ])

        def _set_text(features):
            # .get_buffer() is a bit expensive during startup
            txt_features = self.widgets['txt_features']
            txt_features.get_buffer().set_text(features)
            context = txt_features.get_parent().get_style_context()
            found, background = context.lookup_color('theme_base_color')
            if not found:
                background = context.get_background_color(Gtk.StateType.NORMAL)
            set_widget_bg_color(txt_features, theme.rgba_to_str(background))

        GLib.idle_add(_set_text, features, priority=GLib.PRIORITY_LOW)


    # METHODS #
    def set_banner_image(self, filename):
        self.widgets['img_banner'].set_from_file(filename)


    # SIGNAL HANDLERS #
    def _on_button_clicked(self, button, name):
        self.emit('button-clicked', name)

    def do_style_set(self, previous_style):
        # override_color() is deprecated - match self.get_child()'s
        # foreground to our own via a CSS provider instead.
        child_style = self.get_child().get_style_context()
        if self._child_fg_provider is not None:
            child_style.remove_provider(self._child_fg_provider)
        color = theme.rgba_to_str(self.get_style_context().get_color(Gtk.StateFlags.NORMAL))
        provider = Gtk.CssProvider()
        provider.load_from_data(('* { color: %s; }' % color).encode())
        child_style.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._child_fg_provider = provider

        self._style_widgets()
