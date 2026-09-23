#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.common import SignalTracker
from virtaal.views import rendering
from virtaal.views.baseview import BaseView
from virtaal.views.placeablesguiinfo import StringElemGUI
from virtaal.views.theme import is_inverse

_default_fg = '#006600'
_default_bg = '#eeffee'
_inverse_fg = '#c7ffff'
_inverse_bg = '#003700'

class TerminologyGUIInfo(StringElemGUI):
    """
    GUI info object for terminology placeables. It creates a combo box to
    choose the selected match from.
    """
    # MEMBERS #
    fg = _default_fg
    bg = _default_bg

    def __init__(self, elem, textbox, **kwargs):
        assert elem.__class__.__name__ == 'TerminologyPlaceable'
        super().__init__(elem, textbox, **kwargs)


    # METHODS #
    def get_insert_widget(self):
        if len(self.elem.translations) > 1:
            return TerminologyCombo(self.elem)
        return None

    @classmethod
    def update_style(self, widget):
        from gi.repository import Gtk
        _style = widget.get_style_context()
        fg = _style.get_color(Gtk.StateType.NORMAL)
        found, bg = _style.lookup_color('theme_base_color')
        if not found:
            bg = _style.get_background_color(Gtk.StateType.NORMAL)
        if is_inverse(fg, bg):
            self.fg = _inverse_fg
            self.bg = _inverse_bg
        else:
            self.fg = _default_fg
            self.bg = _default_bg


class TerminologyCombo(Gtk.ComboBox):
    """
    A combo box containing translation matches.
    """

    # INITIALIZERS #
    def __init__(self, elem):
        super().__init__()
        self.elem = elem
        self.insert_iter = None
        self.selected_string = None
        self.set_name('termcombo')
        # Let's make it as small as possible, since we don't want to see the
        # combo at all.
        self.set_size_request(0, 0)
        self.__init_combo()
        cell_renderers = self.get_cells()
        # Set the font correctly for the target
        if cell_renderers:
            cell_renderers[0].props.font_desc = rendering.get_target_font_description()
        self.menu = Gtk.Menu.get_for_attach_widget(self)[0]
        self.menu.connect('selection-done', self._on_selection_done)

    def __init_combo(self):
        self._model = Gtk.ListStore(str)
        for trans in self.elem.translations:
            self._model.append([trans])

        self.set_model(self._model)
        self._renderer = Gtk.CellRendererText()
        self.pack_start(self._renderer, True)
        self.add_attribute(self._renderer, 'text', 0)

        # Force the "appears-as-list" style property to 0
        provider = Gtk.CssProvider()
        provider.load_from_data(b'combobox { -GtkComboBox-appears-as-list: 0; }')
        self.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    # METHODS #
    def inserted(self, insert_iter, anchor):
        self.insert_offset = insert_iter.get_offset()
        self.grab_focus()
        self.popup()

    def insert_selected(self):
        iter = self.get_active_iter()
        if iter:
            self.selected_string = self._model.get_value(iter, 0)

        parent = self.get_parent()
        if parent:
            parent.grab_focus()

        buffer = parent.get_buffer()
        parent.remove(self)
        if self.insert_offset >= 0:
            iterins  = buffer.get_iter_at_offset(self.insert_offset)
            iternext = buffer.get_iter_at_offset(self.insert_offset + 1)
            if iternext:
                buffer.delete(iterins, iternext)

            iterins  = buffer.get_iter_at_offset(self.insert_offset)
            parent.refresh_cursor_pos = buffer.props.cursor_position
            if self.selected_string:
                buffer.insert(iterins, self.selected_string)
                parent.emit("changed")


    # EVENT HANDLERS #
    def _on_selection_done(self, menushell):
        self.insert_selected()


class TerminologyView(BaseView):
    """
    Does general GUI setup for the terminology plug-in.
    """

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self._signal_tracker = SignalTracker()


    # METHODS #
    def destroy(self):
        self._signal_tracker.disconnect_all()

    def select_backends(self, parent):
        from virtaal.views.backendselect import select_backends
        select_backends(
            self.controller.main_controller, self.controller.plugin_controller,
            self.controller.config, 'basetermmodel',
            title=_('Select Terminology Sources'),
            message=_('Select the sources of terminology suggestions'),
            size=(self.controller.config['backends_dialog_width'], 300),
            parent=parent,
        )
