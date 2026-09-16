#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk, Pango

from virtaal.common import SignalTracker
from virtaal.common.utils import get_unicode
from virtaal.views.baseview import BaseView
from virtaal.views.widgets.wordatcursor import WordAtCursorSelector


class LookupView(BaseView):
    """
    Makes look-up models accessible via the source- and target text views'
    context menu.
    """

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self.lang_controller = controller.main_controller.lang_controller

        self._signal_tracker = SignalTracker()
        self._word_selector = WordAtCursorSelector()
        unitview = controller.main_controller.unit_controller.view
        if unitview.sources:
            self._connect_to_textboxes(unitview, unitview.sources)
        else:
            self._signal_tracker.connect(unitview, 'sources-created', self._connect_to_textboxes)
        if unitview.targets:
            self._connect_to_textboxes(unitview, unitview.targets)
        else:
            self._signal_tracker.connect(unitview, 'targets-created', self._connect_to_textboxes)

    def _connect_to_textboxes(self, unitview, textboxes):
        for textbox in textboxes:
            self._signal_tracker.connect(textbox, 'button-press-event', self._word_selector.on_button_press)
            self._signal_tracker.connect(textbox, 'populate-popup', self._on_populate_popup)


    # METHODS #
    def destroy(self):
        self._signal_tracker.disconnect_all()

    def select_backends(self, parent):
        from virtaal.views.backendselect import select_backends
        select_backends(
            self.controller.main_controller, self.controller.plugin_controller,
            self.controller.config, 'baselookupmodel',
            #l10n: The 'services' here refer to different look-up plugins,
            #such as web look-up, etc.
            title=_('Select Look-up Services'),
            message=_('Select the services that should be used to perform look-ups'),
            size=(self.controller.config['backends_dialog_width'], 200),
            parent=parent,
        )


    # SIGNAL HANDLERS #

    def _on_populate_popup(self, textbox, menu):
        buf = textbox.buffer
        if not buf.get_has_selection():
            self._word_selector.select_word_at_cursor(buf)
        if not buf.get_has_selection():
            return

        selection = get_unicode(buf.get_text(*buf.get_selection_bounds(), include_hidden_chars=False)).strip()
        role      = textbox.role
        srclang   = self.lang_controller.source_lang.code
        tgtlang   = self.lang_controller.target_lang.code

        lookup_menu = Gtk.Menu()
        selection_entry = _('Look-up "%(selection)s"') % {'selection': selection}
        menu_item = Gtk.MenuItem(selection_entry)
        # Pango ellipsizes on grapheme clusters, unlike a raw string
        # slice - safer for combining marks (e.g. Arabic niqqud,
        # Devanagari conjuncts) than truncating the string ourselves.
        menu_item.get_child().set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        menu_item.get_child().set_max_width_chars(40)

        plugins = self.controller.plugin_controller.plugins
        top_level_items = []
        nested_items = []
        names = list(plugins.keys())
        names.sort()
        for name in names:
            items = plugins[name].create_menu_items(selection, role, srclang, tgtlang, textbox)
            if getattr(plugins[name], 'TOP_LEVEL', False):
                top_level_items.extend(items)
            else:
                nested_items.extend(items)
        if not top_level_items and not nested_items:
            return

        sep = Gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)

        for i in top_level_items:
            i.show_all()
            menu.append(i)

        if nested_items:
            for i in nested_items:
                lookup_menu.append(i)
            menu_item.set_submenu(lookup_menu)
            menu_item.show_all()
            menu.append(menu_item)
