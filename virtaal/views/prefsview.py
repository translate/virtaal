#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gdk, GLib, GObject, Gtk, Pango

from virtaal.common import GObjectWrapper, pan_app
from virtaal.common.platform import platform
from virtaal.views.widgets.selectview import SelectView

from .baseview import BaseView


class PreferencesView(BaseView, GObjectWrapper):
    """Load, display and control the "Preferences" dialog."""

    __gtype_name__ = 'PreferencesView'
    __gsignals__ = {
        'prefs-done': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)
        self.controller = controller
        self._widgets = {}
        self._setup_key_bindings()
        self._setup_menu_item()

    def _get_widgets(self):
        self.gui = self.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='PreferencesDlg',
            domain="virtaal"
        )

        widget_names = (
            'btn_default_fonts', 'cmb_ui_language', 'ent_email', 'ent_team', 'ent_translator',
            'fbtn_source', 'fbtn_target', 'scrwnd_placeables', 'scrwnd_plugins',
        )
        for name in widget_names:
            self._widgets[name] = self.gui.get_object(name)

        self._widgets['dialog'] = self.gui.get_object('PreferencesDlg')
        self._widgets['dialog'].set_transient_for(self.controller.main_controller.view.main_window)
        self._widgets['dialog'].set_icon(self.controller.main_controller.view.main_window.get_icon())
        if platform.is_mac:
            self._widgets['dialog'].set_title(_('Settings'))

    def _init_gui(self):
        self._get_widgets()
        self._init_font_gui()
        self._init_language_gui()
        self._init_placeables_page()
        self._init_plugins_page()

    def _init_language_gui(self):
        self._widgets['cmb_ui_language'].append('', _('System default'))
        for code, name in pan_app.get_available_ui_languages():
            self._widgets['cmb_ui_language'].append(code, name)

    def _init_font_gui(self):
        def reset_fonts(button):
            self._widgets['fbtn_source'].set_font_name(pan_app.get_default_font())
            self._widgets['fbtn_target'].set_font_name(pan_app.get_default_font())
        self._widgets['btn_default_fonts'].connect('clicked', reset_fonts)

        for fbtn in (self._widgets['fbtn_source'], self._widgets['fbtn_target']):
            fbtn.connect('clicked', self._on_font_button_clicked)

    def _on_font_button_clicked(self, fbtn):
        # GtkFontButton manages its own internal GtkFontChooserDialog with
        # no public accessor for it, so find the dialog it just opened via
        # the toplevel window list to manage its focus like every other
        # dialog in this view (present()/restore-focus - see the rest of
        # this file and its sibling dialogs for the same pattern).
        def find_and_present():
            prefs_dialog = self._widgets['dialog']
            for window in Gtk.Window.list_toplevels():
                if window is prefs_dialog or not window.get_visible():
                    continue
                if isinstance(window, Gtk.Dialog) and window.get_transient_for() is prefs_dialog:
                    window.present()
                    window.connect('hide', lambda w: GLib.idle_add(prefs_dialog.present))
                    break
            return False
        GLib.idle_add(find_and_present)

    def _init_placeables_page(self):
        self.placeables_select = SelectView()
        self.placeables_select.connect('item-enabled', self._on_placeable_toggled)
        self.placeables_select.connect('item-disabled', self._on_placeable_toggled)
        self._widgets['scrwnd_placeables'].set_propagate_natural_width(True)
        # The .ui file marks this focusable, which swallows Tab/Down
        # meant for the list inside it - the scroller chrome itself
        # has no reason to be a stop in the focus chain.
        self._widgets['scrwnd_placeables'].set_can_focus(False)
        self._widgets['scrwnd_placeables'].add(self.placeables_select)
        self._widgets['scrwnd_placeables'].show_all()

    def _init_plugins_page(self):
        self.plugins_select = SelectView()
        self.plugins_select.connect('item-enabled', self._on_plugin_toggled)
        self.plugins_select.connect('item-disabled', self._on_plugin_toggled)
        self._widgets['scrwnd_plugins'].set_propagate_natural_width(True)
        self._widgets['scrwnd_plugins'].set_can_focus(False)
        self._widgets['scrwnd_plugins'].add(self.plugins_select)
        self._widgets['scrwnd_plugins'].show_all()

    def _setup_key_bindings(self):
        # Comma, not "p" - Cmd+, is the macOS system convention for
        # Preferences, translated from Ctrl+, the same way every other
        # accelerator here relies on GtkosxApplication's Ctrl->Cmd mapping.
        Gtk.AccelMap.add_entry("<Virtaal>/Edit/Preferences", Gdk.KEY_comma, Gdk.ModifierType.CONTROL_MASK)

    def _setup_menu_item(self):
        mainview = self.controller.main_controller.view
        menu_edit = mainview.gui.get_object('menu_edit')
        mnu_prefs = mainview.gui.get_object('mnu_prefs')

        accel_group = menu_edit.get_accel_group()
        if accel_group is None:
            accel_group = Gtk.AccelGroup()
            menu_edit.set_accel_group(accel_group)
            mainview.add_accel_group(accel_group)

        mnu_prefs.set_accel_path("<Virtaal>/Edit/Preferences")
        mnu_prefs.connect('activate', self._show_preferences)
        mainview.sync_menubar()

        # Preferences is moved into macOS's native App Menu (see
        # mainview.py's insert_app_menu_item()), which never picks up a
        # key equivalent from accel_path/AccelMap the way the regular
        # menu bar does - so the Ctrl-then-Quartz-translates-to-Cmd
        # convention every other shortcut here relies on never fires.
        # Real Cmd+comma arrives as META_MASK|MOD2_MASK, not
        # CONTROL_MASK - bind that directly instead.
        accel_group.connect(Gdk.KEY_comma, Gdk.ModifierType.META_MASK | Gdk.ModifierType.MOD2_MASK,
                             Gtk.AccelFlags.VISIBLE, self._show_preferences)

    # ACCESSORS #
    def _get_font_data(self):
        return {
            'source': self._widgets['fbtn_source'].get_font_name(),
            'target': self._widgets['fbtn_target'].get_font_name(),
        }
    def _set_font_data(self, value):
        if not isinstance(value, dict) or not 'source' in value or not 'target' in value:
            raise ValueError('Value must be a dictionary')
        sourcefont = Pango.FontDescription(value['source'])
        targetfont = Pango.FontDescription(value['target'])
        self._widgets['fbtn_source'].set_font_name(value['source'])
        self._widgets['fbtn_target'].set_font_name(value['target'])
    font_data = property(_get_font_data, _set_font_data)

    def _get_placeables_data(self):
        return self.placeables_select.get_all_items()
    def _set_placeables_data(self, value):
        selected = self.placeables_select.get_selected_item()
        scroll = self.placeables_select.get_scroll_position()
        self.placeables_select.set_model(value)
        self.placeables_select.select_item(selected)
        # GTK defers scrolling the reselected row into view until it's
        # revalidated the rebuilt model's row heights (its own idle
        # callback) - restoring the old position synchronously here
        # gets overwritten by that once it runs. Queue behind it.
        GLib.idle_add(self.placeables_select.set_scroll_position, scroll)
    placeables_data = property(_get_placeables_data, _set_placeables_data)

    def _get_plugin_data(self):
        return self.plugins_select.get_all_items()
    def _set_plugin_data(self, value):
        selected = self.plugins_select.get_selected_item()
        scroll = self.plugins_select.get_scroll_position()
        self.plugins_select.set_model(value)
        self.plugins_select.select_item(selected)
        GLib.idle_add(self.plugins_select.set_scroll_position, scroll)
    plugin_data = property(_get_plugin_data, _set_plugin_data)

    def _get_ui_language(self):
        return self._widgets['cmb_ui_language'].get_active_id() or ''
    def _set_ui_language(self, value):
        self._widgets['cmb_ui_language'].set_active_id(value or '')
    ui_language = property(_get_ui_language, _set_ui_language)

    def _get_user_data(self):
        return {
            'name':  self._widgets['ent_translator'].get_text(),
            'email': self._widgets['ent_email'].get_text(),
            'team':  self._widgets['ent_team'].get_text()
        }
    def _set_user_data(self, value):
        if not isinstance(value, dict):
            raise ValueError('Value must be a dictionary')
        if 'name' in value:
            self._widgets['ent_translator'].set_text(value['name'] or '')
        if 'email' in value:
            self._widgets['ent_email'].set_text(value['email'] or '')
        if 'team' in value:
            self._widgets['ent_team'].set_text(value['team'] or '')
    user_data = property(_get_user_data, _set_user_data)


    # METHODS #
    def show(self):
        if not self._widgets:
            self._init_gui()
        self.placeables_select.select_item(None)
        self.plugins_select.select_item(None)
        self.controller.update_prefs_gui_data()
        #logging.debug('Plug-in data: %s' % (str(self.plugin_data)))
        # present() only raises/focuses an already-realized window -
        # show() explicitly first, run() alone doesn't guarantee that.
        self._widgets['dialog'].show()
        self._widgets['dialog'].present()
        transient_for = self._widgets['dialog'].get_transient_for()
        self._widgets['dialog'].run()
        self._widgets['dialog'].hide()
        if transient_for is not None:
            GLib.idle_add(transient_for.present)
        self.emit('prefs-done')


    # EVENT HANDLERS #
    def _on_placeable_toggled(self, sview, item):
        self.controller.set_placeable_enabled(
            parser=item['data'],
            enabled=item['enabled']
        )

    def _on_plugin_toggled(self, sview, item):
        self.controller.set_plugin_enabled(
            plugin_name=item['data']['internal_name'],
            enabled=item['enabled']
        )

    def _show_preferences(self, *args):
        self.show()
