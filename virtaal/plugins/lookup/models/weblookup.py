#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from os import path
from urllib import parse


def _slugify(display_name):
    """A stable id derived from a user's own typed name, so they're
        never asked for one directly - "My Site" -> "my_site"."""
    return display_name.strip().lower().replace(' ', '_')

from gi.repository import GLib, Gtk, Pango

from virtaal.common import pan_app
from virtaal.views.baseview import BaseView

try:
    from virtaal.plugins.lookup.models.baselookupmodel import BaseLookupModel
except ImportError:
    from virtaal_plugins.lookup.models.baselookupmodel import BaseLookupModel


class LookupModel(BaseLookupModel):
    """Look-up the selected string on the web."""

    __gtype_name__ = 'WebLookupModel'
    #l10n: plugin name
    display_name = _('Web Look-up')
    description = _('Look-up the selected text on a web site')

    URLDATA = [
        {
            'id': 'google',
            'display_name': _('Google'),
            'url': 'http://www.google.com/search?q=%(query)s',
            'quoted': True,
            'enabled': True,
        },
        {
            'id': 'wikipedia',
            'display_name': _('Wikipedia'),
            'url': 'http://%(querylang)s.wikipedia.org/wiki/%(query)s',
            'quoted': False,
            'enabled': True,
        },
        {
            'id': 'wiktionary',
            'display_name': _('Wiktionary'),
            'url': 'http://%(querylang)s.wiktionary.org/wiki/%(query)s',
            'quoted': False,
            'enabled': True,
        },
        # Redundant with Google for the search-engine case - shipped
        # disabled rather than left out entirely, so enabling one is a
        # checkbox away instead of needing to know the URL to add it
        # by hand.
        {
            'id': 'bing',
            'display_name': _('Bing'),
            'url': 'http://www.bing.com/search?q=%(query)s',
            'quoted': True,
            'enabled': False,
        },
        {
            'id': 'yahoo',
            'display_name': _('Yahoo'),
            'url': 'http://search.yahoo.com/search?p=%(query)s',
            'quoted': True,
            'enabled': False,
        },
    ]
    """A list of dictionaries containing data about each URL:
    * C{id}: A stable, untranslated identifier - used as the saved
        config's own key instead of C{display_name}, which changes
        with the UI language. Absent on a user's own custom entry,
        whose C{display_name} is untranslated free text anyway and
        so already stable enough to serve as its own id.
    * C{display_name}: The name that will be shown in the context menu
    * C{url}: The actual URL that will be queried. See below for template
        variables.
    * C{quoted}: Whether or not the query string should be put in quotes (").
    * C{enabled}: Whether this look-up is offered at all.

    Valid template variables in 'url' fields are:
    * C{%(query)s}: The selected text that makes up the look-up query.
    * C{%(querylang)s}: The language of the query string (one of C{%(srclang)s}
        or C{%(tgtlang)s}).
    * C{%(nonquerylang)s}: The source- or target language which is B{not} the
        language that the query (selected text) is in.
    * C{%(srclang)s}: The currently selected source language.
    * C{%(tgtlang)s}: The currently selected target language.
    """

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.controller = controller
        self.internal_name = internal_name

        self.configure_func = self.configure
        self.urldata_file = path.join(pan_app.get_config_dir(), "weblookup.ini")

        self._load_urldata()

    def _load_urldata(self):
        urls = list(pan_app.load_config(self.urldata_file).values())
        if urls:
            # A save from before 'id' existed has none - resolve it by
            # matching its own (untranslated, at the time) display_name
            # against the current defaults'. A genuinely custom entry
            # matches nothing here and gets one derived the same way a
            # newly-added one would.
            display_to_id = {d['display_name']: d['id'] for d in type(self).URLDATA}
            for u in urls:
                if 'quoted' in u:
                    u['quoted'] = u['quoted'] == 'True'
                # A saved entry from before this key existed has no
                # 'enabled' value - default it to enabled.
                u['enabled'] = u.get('enabled', 'True') == 'True'
                u.setdefault('id', display_to_id.get(u['display_name'], _slugify(u['display_name'])))
            saved_ids = {u['id'] for u in urls}
            urls += [u for u in type(self).URLDATA if u['id'] not in saved_ids]
            self.URLDATA = urls


    # METHODS #
    def configure(self, parent):
        configure_dialog = WebLookupConfigDialog(parent.get_toplevel())
        configure_dialog.urldata = self.URLDATA
        configure_dialog.run()
        self.URLDATA = configure_dialog.urldata
        self._save_urldata()

    def create_menu_items(self, query, role, srclang, tgtlang, textbox):
        querylang = role == 'source' and srclang or tgtlang
        nonquerylang = role != 'source' and srclang or tgtlang
        query = parse.quote(query.encode('utf-8'))
        items = []
        for urlinfo in self.URLDATA:
            if not urlinfo.get('enabled', True):
                continue
            uquery = query
            if 'quoted' in urlinfo and urlinfo['quoted']:
                uquery = '"' + uquery + '"'

            i = Gtk.MenuItem(label=urlinfo['display_name'])
            lookup_str = urlinfo['url'] % {
                'query':        uquery,
                'querylang':    querylang,
                'nonquerylang': nonquerylang,
                'srclang':      srclang,
                'tgtlang':      tgtlang
            }
            i.connect('activate', self._on_lookup, lookup_str)
            items.append(i)
        return items

    def _save_urldata(self):
        # Keyed by id, not display_name - the section name must stay
        # stable across a UI language change, unlike the translated
        # display_name.
        config = dict([ (u.get('id', u['display_name']), u) for u in self.URLDATA ])
        pan_app.save_config(self.urldata_file, config)

    def destroy(self):
        self._save_urldata()


    # SIGNAL HANDLERS #
    def _on_lookup(self, menuitem, url):
        from virtaal.support.openmailto import open
        open(url)


class WebLookupConfigDialog:
    """Dialog manages the URLs used by the web look-up plug-in."""

    COL_ENABLED, COL_NAME, COL_URL, COL_QUOTE, COL_DATA = range(5)

    # INITIALIZERS #
    def __init__(self, parent):
        self.gui = BaseView.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='WebLookupManager',
            domain='virtaal'
        )

        self._get_widgets()
        if isinstance(parent, Gtk.Widget):
            self.dialog.set_transient_for(parent)
            self.dialog.set_icon(parent.get_toplevel().get_icon())

        already_initialized = bool(self.tvw_urls.get_columns())
        if not already_initialized:
            self._init_widgets()
            self._init_treeview()
        self.lst_urls = self.tvw_urls.get_model()

    def _get_widgets(self):
        widget_names = ('btn_url_add', 'btn_url_remove', 'tvw_urls')

        for name in widget_names:
            setattr(self, name, self.gui.get_object(name))

        self.dialog = self.gui.get_object('WebLookupManager')
        self.add_dialog = WebLookupAddDialog(self.dialog)

    def _init_treeview(self):
        # The .ui file marks this focusable, swallowing Tab/Down meant
        # for the treeview inside it.
        self.tvw_urls.get_parent().set_can_focus(False)

        self.lst_urls = Gtk.ListStore(bool, str, str, bool, object)
        self.tvw_urls.set_model(self.lst_urls)

        cell = Gtk.CellRendererToggle()
        cell.set_radio(False)
        cell.connect('toggled', self._on_enabled_toggled)
        #l10n: Whether this look-up is offered at all
        col = Gtk.TreeViewColumn(_('Enabled'))
        col.pack_start(cell, True)
        col.add_attribute(cell, 'active', self.COL_ENABLED)
        self.tvw_urls.append_column(col)

        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Name'))
        col.pack_start(cell, True)
        col.add_attribute(cell, 'text', self.COL_NAME)
        col.props.resizable = True
        col.set_sort_column_id(1)
        self.tvw_urls.append_column(col)

        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.MIDDLE
        col = Gtk.TreeViewColumn(_('URL'))
        col.pack_start(cell, True)
        col.add_attribute(cell, 'text', self.COL_URL)
        col.props.resizable = True
        col.set_expand(True)
        col.set_sort_column_id(2)
        self.tvw_urls.append_column(col)

        cell = Gtk.CellRendererToggle()
        cell.set_radio(False)
        cell.connect('toggled', self._on_quote_toggled)
        #l10n: Whether the selected text should be surrounded by "quotes"
        col = Gtk.TreeViewColumn(_('Quote Query'))
        col.pack_start(cell, True)
        col.add_attribute(cell, 'active', self.COL_QUOTE)
        self.tvw_urls.append_column(col)

    def _init_widgets(self):
        self.btn_url_add.connect('clicked', self._on_add_clicked)
        self.btn_url_remove.connect('clicked', self._on_remove_clicked)


    # ACCESSORS #
    def _get_urldata(self):
        return [row[self.COL_DATA] for row in self.lst_urls]
    def _set_urldata(self, value):
        self.lst_urls.clear()
        for url in value:
            self.lst_urls.append((url.get('enabled', True), url['display_name'], url['url'], url['quoted'], url))
    urldata = property(_get_urldata, _set_urldata)


    # METHODS #
    def run(self, parent=None):
        if isinstance(parent, Gtk.Widget):
            self.dialog.set_transient_for(parent)

        self.dialog.show()
        self.dialog.present()
        transient_for = self.dialog.get_transient_for()
        self.dialog.run()
        self.dialog.hide()
        if transient_for is not None:
            GLib.idle_add(transient_for.present)


    # SIGNAL HANDLERS #
    def _on_add_clicked(self, button):
        url = self.add_dialog.run()
        if url is None:
            return
        self.lst_urls.append((url['enabled'], url['display_name'], url['url'], url['quoted'], url))

    def _on_remove_clicked(self, button):
        selected = self.tvw_urls.get_selection().get_selected()
        if not selected or not selected[1]:
            return
        selected[0].remove(selected[1])

    def _on_enabled_toggled(self, cell, path):
        new_value = not self.lst_urls[path][self.COL_ENABLED]
        self.lst_urls[path][self.COL_ENABLED] = new_value
        self.lst_urls[path][self.COL_DATA]['enabled'] = new_value

    def _on_quote_toggled(self, cell, path):
        new_value = not self.lst_urls[path][self.COL_QUOTE]
        self.lst_urls[path][self.COL_QUOTE] = new_value
        self.lst_urls[path][self.COL_DATA]['quoted'] = new_value


class WebLookupAddDialog:
    """The dialog used to add URLs for the web look-up plug-in."""

    # INITIALIZERS #
    def __init__(self, parent):
        self.gui = BaseView.load_builder_file(
            ["virtaal", "virtaal.ui"],
            root='WebLookupAdd',
            domain='virtaal'
        )
        self._get_widgets()

        if isinstance(parent, Gtk.Window):
            self.dialog.set_transient_for(parent)
            self.dialog.set_icon(parent.get_toplevel().get_icon())

    def _get_widgets(self):
        widget_names = ('btn_url_cancel', 'btn_url_ok', 'cbtn_url_quote', 'ent_url_name', 'ent_url')

        for name in widget_names:
            setattr(self, name, self.gui.get_object(name))

        self.dialog = self.gui.get_object('WebLookupAdd')


    # METHODS #
    def run(self):
        self.ent_url.set_text('')
        self.ent_url_name.set_text('')
        self.cbtn_url_quote.set_active(False)
        self.ent_url_name.grab_focus()

        self.dialog.show()
        self.dialog.present()
        transient_for = self.dialog.get_transient_for()
        response = self.dialog.run()
        self.dialog.hide()
        if transient_for is not None:
            GLib.idle_add(transient_for.present)

        if response != Gtk.ResponseType.OK:
            return None

        name = self.ent_url_name.get_text()
        self.url = {
            'id':             _slugify(name),
            'display_name':   name,
            'url':            self.ent_url.get_text(),
            'quoted':         self.cbtn_url_quote.get_active(),
            'enabled':        True,
        }
        return self.url
