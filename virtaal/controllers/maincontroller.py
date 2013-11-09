#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
# Copyright 2013 F Wolff
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
from gobject import SIGNAL_RUN_FIRST

from virtaal.common import GObjectWrapper, pan_app
from virtaal.views.mainview import MainView

from basecontroller import BaseController


class MainController(BaseController):
    """The main controller that initializes the others and contains the main
        program loop."""

    __gtype_name__ = 'MainController'
    __gsignals__ = {
        'controller-registered': (SIGNAL_RUN_FIRST, None, (object,)),
        'quit':                  (SIGNAL_RUN_FIRST, None, tuple()),
    }

    # INITIALIZERS #
    def __init__(self):
        GObjectWrapper.__init__(self)
        self._force_saveas = False

        self._checks_controller = None
        self._lang_controller = None
        self._mode_controller = None
        self._placeables_controller = None
        self._plugin_controller = None
        self._store_controller = None
        self._undo_controller = None
        self._unit_controller = None
        self._welcomescreen_controller = None
        self.view = MainView(self)

    def load_plugins(self):
        # Helper method to be called from virtaal.main
        if self.plugin_controller:
            self.plugin_controller.load_plugins()

    def destroy(self):
        self.store_controller.destroy()


    # ACCESSORS #
    def get_store(self):
        """Returns the store model of the current open translation store or C{None}."""
        return self.store_controller.get_store()

    def get_store_filename(self):
        """C{self.store_controller.get_store_filename()}"""
        return self.store_controller.get_store_filename()

    def get_translator_name(self):
        name = pan_app.settings.translator["name"]
        if not name:
            return self.show_input(
                title=_('Header information'),
                msg=_('Please enter your name')
            )
        return name

    def get_translator_email(self):
        email = pan_app.settings.translator["email"]
        if not email:
            return self.show_input(
                title=_('Header information'),
                msg=_('Please enter your e-mail address')
            )
        return email

    def get_translator_team(self):
        team = pan_app.settings.translator["team"]
        if not team:
            return self.show_input(
                title=_('Header information'),
                msg=_("Please enter your team's information")
            )
        return team

    def set_saveable(self, value):
        self.view.set_saveable(value)

    def set_force_saveas(self, value):
        self._force_saveas = value

    def get_force_saveas(self):
        return self._force_saveas

    def _get_checks_controller(self):
        return self._checks_controller
    def _set_checks_controller(self, value):
        self._checks_controller = value
        self.emit('controller-registered', self._checks_controller)
    checks_controller = property(_get_checks_controller, _set_checks_controller)

    def _get_lang_controller(self):
        return self._lang_controller
    def _set_lang_controller(self, value):
        self._lang_controller = value
        self.emit('controller-registered', self._lang_controller)
    lang_controller = property(_get_lang_controller, _set_lang_controller)

    def _get_mode_controller(self):
        return self._mode_controller
    def _set_mode_controller(self, value):
        self._mode_controller = value
        self.emit('controller-registered', self._mode_controller)
    mode_controller = property(_get_mode_controller, _set_mode_controller)

    def _get_placeables_controller(self):
        return self._placeables_controller
    def _set_placeables_controller(self, value):
        self._placeables_controller = value
        self.emit('controller-registered', self._placeables_controller)
    placeables_controller = property(_get_placeables_controller, _set_placeables_controller)

    def _get_plugin_controller(self):
        return self._plugin_controller
    def _set_plugin_controller(self, value):
        self._plugin_controller = value
        self.emit('controller-registered', self._plugin_controller)
    plugin_controller = property(_get_plugin_controller, _set_plugin_controller)

    def _get_store_controller(self):
        return self._store_controller
    def _set_store_controller(self, value):
        self._store_controller = value
        self.emit('controller-registered', self._store_controller)
    store_controller = property(_get_store_controller, _set_store_controller)

    def _get_undo_controller(self):
        return self._undo_controller
    def _set_undo_controller(self, value):
        self._undo_controller = value
        self.emit('controller-registered', self._undo_controller)
    undo_controller = property(_get_undo_controller, _set_undo_controller)

    def _get_unit_controller(self):
        return self._unit_controller
    def _set_unit_controller(self, value):
        self._unit_controller = value
        self.emit('controller-registered', self._unit_controller)
    unit_controller = property(_get_unit_controller, _set_unit_controller)

    def _get_welcomescreen_controller(self):
        return self._welcomescreen_controller
    def _set_welcomescreen_controller(self, value):
        self._welcomescreen_controller = value
        self.emit('controller-registered', self._welcomescreen_controller)
    welcomescreen_controller = property(_get_welcomescreen_controller, _set_welcomescreen_controller)


    # METHODS #
    def open_file(self, filename=None, uri='', forget_dir=False):
        """Open the file given by C{filename}.
            @returns: The filename opened, or C{None} if an error has occurred."""
        # We might be a bit early for some of the other controllers, so let's
        # make it our problem and ensure the last ones are in the main
        # controller.
        while not self.placeables_controller:
            gtk.main_iteration(False)
        if filename is None:
            return self.view.open_file()
        if self.store_controller.is_modified():
            response = self.view.show_save_confirm_dialog()
            if response == 'save':
                if not self.save_file():
                    return False
            elif response == 'cancel':
                return False
            # Unnecessary to test for 'discard'

        if filename.startswith('file://'):
            if os.name == "nt":
                filename = filename[len('file:///'):]
            else:
                filename = filename[len('file://'):]

        if self.store_controller.store and self.store_controller.store.get_filename() == filename:
            promptmsg = _('You selected the currently open file for opening. Do you want to reload the file?')
            if not self.show_prompt(msg=promptmsg):
                return False

        try:
            self.store_controller.open_file(filename, uri, forget_dir=forget_dir)
            self.mode_controller.refresh_mode()
            return True
        except Exception, exc:
            import logging
            logging.exception('MainController.open_file(filename="%s", uri="%s")' % (filename, uri))
            self.show_error(
                filename + ":\n" + _("Could not open file.\n\n%(error_message)s\n\nTry opening a different file.") % {'error_message': str(exc)}
            )
            return False

    def open_tutorial(self):
        # Save on the disk a localized version of the tutorial using the
        # current locale.
        from virtaal.support.tutorial import create_localized_tutorial
        filename = create_localized_tutorial()

        # Open the file just created on the fly.
        self.open_file(filename, forget_dir=True)


    def save_file(self, filename=None, force_saveas=False):
        # we return True on success
        if not filename and (self.get_force_saveas() or force_saveas):
            filename = self.store_controller.get_bundle_filename()
            if filename is None:
                filename = self.get_store_filename() or ''
            filename = self.view.show_save_dialog(current_filename=filename, title=_("Save"))
            if not filename:
                return False

        if self._do_save_file(filename):
            if self.get_force_saveas():
                self.set_force_saveas(False)
            return True
        else:
            return False

    def _do_save_file(self, filename=None):
        """Delegate saving to the store_controller, but do error handling.

        Return True on success, False otherwise."""
        try:
            self.store_controller.save_file(filename)
            return True
        except IOError, exc:
            self.show_error(
                _("Could not save file.\n\n%(error_message)s\n\nTry saving to a different location.") % {'error_message': str(exc)}
            )
        except Exception, exc:
            import logging
            logging.exception('MainController.save_file(filename="%s")' % (filename))
            self.show_error(
                _("Could not save file.\n\n%(error_message)s" % {'error_message': str(exc)})
            )
        return False

    def binary_export(self):
        #let's try to suggest a filename:
        filename = self.store_controller.get_bundle_filename()
        if filename is None:
            filename = self.get_store_filename() or ''
        if not (filename.endswith('.po') or filename.endswith('.po.bz2') or filename.endswith('.po.gz')):
            self.show_error(
                _("Can only export Gettext PO files")
            )
            return False

        if filename.endswith('.po'):
            #TODO: do something better, especially for files like fr.po and gnome-shell.po.master.fr.po
            filename = filename[:-3] + '.mo'
        else:
            filename = 'messages.mo'
        filename = self.view.show_save_dialog(current_filename=filename, title=_("Export"))
        if not filename:
            return False
        try:
            self.store_controller.binary_export(filename)
            return True
        except IOError, exc:
            self.show_error(
                _("Could not export file.\n\n%(error_message)s\n\nTry saving to a different location.") % {'error_message': str(exc)}
            )
        except Exception, exc:
            import logging
            logging.exception('MainController.binary_export(filename="%s")' % (filename))
            self.show_error(
                _("Could not export file.\n\n%(error_message)s" % {'error_message': str(exc)})
            )
        return False

    def close_file(self):
        if self.store_controller.is_modified():
            response = self.view.show_save_confirm_dialog()
            if response == 'save':
                if not self.save_file():
                    return False
            elif response == 'cancel':
                return False
            # Unnecessary to test for 'discard'
        self.store_controller.close_file()

    def revert_file(self, filename=None):
        confirm = self.show_prompt(_("Reload File"), _("Reload file from last saved copy and lose all changes?"))
        if not confirm:
            return

        try:
            self.store_controller.revert_file()
            self.mode_controller.refresh_mode()
        except Exception, exc:
            import logging
            logging.exception('MainController.revert_file(filename="%s")' % (filename))
            self.show_error(
                _("Could not open file.\n\n%(error_message)s\n\nTry opening a different file.") % {'error_message': str(exc)}
            )

    def update_file(self, filename, uri=''):
        """Update the current file using the file given by C{filename} as template.
            @returns: The filename opened, or C{None} if an error has occurred."""
        if self.store_controller.is_modified():
            response = self.view.show_save_confirm_dialog()
            if response == 'save':
                if not self.save_file():
                    return False
            elif response == 'cancel':
                return False
            # Unnecessary to test for 'discard'

        if self.store_controller.store and self.store_controller.store.get_filename() == filename:
            promptmsg = _('You selected the currently open file for opening. Do you want to reload the file?')
            if not self.show_prompt(msg=promptmsg):
                return False

        try:
            self.store_controller.update_file(filename, uri)
            self.mode_controller.refresh_mode()
            return True
        except Exception, exc:
            import logging
            logging.exception('MainController.update_file(filename="%s", uri="%s")' % (filename, uri))
            self.show_error(
                _("Could not open file.\n\n%(error_message)s\n\nTry opening a different file.") % {'error_message': str(exc)}
            )
            return False

    def select_unit(self, unit, force=False):
        """Select the specified unit in the store view."""
        self.store_controller.select_unit(unit, force)

    def show_error(self, msg):
        """Shortcut for C{self.view.show_error_dialog()}"""
        return self.view.show_error_dialog(message=msg)

    def show_input(self, title='', msg=''):
        """Shortcut for C{self.view.show_input_dialog()}"""
        return self.view.show_input_dialog(title=title, message=msg)

    def show_prompt(self, title='', msg=''):
        """Shortcut for C{self.view.show_prompt_dialog()}"""
        return self.view.show_prompt_dialog(title=title, message=msg)

    def show_info(self, title='', msg=''):
        """Shortcut for C{self.view.show_info_dialog()}"""
        return self.view.show_info_dialog(title=title, message=msg)

    def quit(self, force=False):
        if self.store_controller.is_modified() and not force:
            response = self.view.show_save_confirm_dialog()
            if response == 'save':
                if not self.save_file():
                    return False
            elif response != 'discard':
                return True

        self.view.hide()
        if self.plugin_controller:
            self.plugin_controller.shutdown()
        self.emit('quit')
        self.view.quit()
        return False

    def run(self):
        self.view.show()
