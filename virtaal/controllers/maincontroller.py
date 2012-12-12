#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
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

import logging
import os.path
import gtk
from gobject import SIGNAL_RUN_FIRST

from translate.storage import factory

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
            logging.exception('MainController.open_file(filename="%s", uri="%s")' % (filename, uri))
            self.show_error(
                filename + ":\n" + _("Could not open file.\n\n%(error_message)s\n\nTry opening a different file.") % {'error_message': str(exc)}
            )
            return False

    def open_tutorial(self):
        # Entries in the tutorial, now with translated comments
        entries = (
        (_(u"""Welcome to the Virtaal tutorial. You can do the first \
translation by typing just the translation for \"Welcome\". Then press \
Enter."""), 
        u"Welcome", u""),
        
        (_(u"Translate this slightly longer message. If a spell checker is \
available, spelling mistakes are indicated similarly to word processors. Make \
sure the correct language is selected in the bottom right of the window."), 
        u"With this file you can learn about translation using Virtaal", u""),
        
        (_(u"This tutorial will show you some of the things you might want to \
pay attention to while translating software programs. It will help you to \
avoid some problems and produce translations of a higher quality."), 
        u"Quality is important", u""),
        
        (_(u"Some of the advice will only be relevant to some languages. For \
example, if your language does not use the Latin alphabet, some of the advice \
might not be relevant to translation in your language. For many languages \
there are established translation rules."), 
        u"Languages are different", u""),
        
        (_(u"The correct use of capital letters are important in many \
languages. Translate this message with careful attention to write \"Virtaal\" \
with a capital letter."), 
        u"The product we use is called Virtaal", u""),
        
        (_(u"In this message the English uses a capital letter for almost \
every word. Almost no other language uses this style. Unless your language \
definitely needs to follow the English style (also called Title Case), \
translate this by following the normal capitalisation rules for your language. \
If your language does not use capital letters, simply translate it normally."), 
        u"Download the File Now", u""),
        
        (_(u"If you translated the previous message you should see a window \
with that translation and a percentage indicating how similar the source \
strings (English) are. It is Virtaal's translation memory at work. Press \
Control+1 to copy the suggested translation to the current translation. \
Remember to always review suggestions before you use them."), 
        u"Download the files now", u""),
        
        (_(u"This is a simple message that starts with a capital letter in \
English. If your language uses capital letters, you almost definitely want to \
start your translation with a capital letter as well."), 
        u"Time", u""),
        
        (_(u"This is a simple message that starts with a lower case letter in \
English. If your language uses capital letters, you almost definitely want to \
start your translation with a lower case letter as well."), 
        u"later", u""),
        
        (_(u"This message is a question. Make sure that you use the correct \
question mark in your translation as well."), 
        u"What is your name?", u""),
        
        (_(u"This message is a label as part of a form. Note how it ends with \
a colon (:)."), 
        u"Name:", u""),
        
        (_(u"If the source will remain mostly or completely unchanged it is \
convenient to copy the entire source string with Alt+Down. Here is almost \
nothing to translate, so just press Alt+Down and make corrections if \
necessary."), 
        u"<b><a href=\"http://virtaal.org/\">Virtaal</a></b>", u""),
        
        (_(u"Placeables are special parts of the text, like the © symbol, that \
can be automatically highlighted and easily inserted into the translation. \
Select the © with Alt+Right and transfer it to the target with Alt+Down."), 
        u"© Virtaal Team", u""),
        
        (_(u"Recognised placeables include special symbols, numbers, variable \
place holders, acronyms and many more. Move to each one with Alt+Right and \
transfer it down with Alt+Down."), 
        u"© 2009 contributors", u""),
        
        (_(u"This message ends with ... to indicate that clicking on this text \
will cause a dialogue to appear instead of just performing an action. Be sure \
to end your message with ... as well."), 
        u"Save As...", u""),
        
        (_(u"This message ends with a special character that looks like three \
dots. Select the special character with Alt+Right and copy it to your \
translation with Alt+Down. Don't just type three dot characters."), 
        u"Save As…", u""),
        
        (_(u"This message has two sentences. Translate them and make sure you \
start each with a capital letter if your language uses them, and end each \
sentence properly."), 
        u"Always try your best. Many people are available to learn from.", u""),
        
        (_(u"This message marks the word \"now\" as important with bold tags. \
These tags can be transferred from the source with Alt+Right and Alt+Down. \
Leave the <b> and </b> in the translation around the part that corresponds to \
\"now\". Read more about XML markup here: http://en.wikipedia.org/wiki/XML"), 
        u"Restart the program <b>now</b>", u""),
        
        (_(u"This message is very similar to the previous message. Use the \
suggestion of the previous translation with Ctrl+1. Note how the only \
difference is that this one ends with a full stop after the last tag."), 
        u"Restart the program <b>now</b>.", u""),
        
        (_(u"In this message \"%d\" is a placeholder (variable) that \
represents a number. Make sure your translation contains \"%d\" somewhere. In \
this case it refers a number of files. When this message is used the \"%d\" \
will be replaced with a number e.g. 'Number of files copied: 5'.  Note that \
\"%d\" does not refer to a percentage."), 
        u"Number of files copied: %d", u""),
        
        (_(u"In this message, \"%d\" refers again to the number of files, but \
note how the \"(s)\" is used to show that we don't know how many it will be. \
This is often hard to translate well. If you encounter this in software \
translation, you might want to hear from developers if this can be avoided. \
Read more about this and decide how to do it in your language: \
http://translate.sourceforge.net/wiki/guide/translation/plurals"), 
        u"%d file(s) will be downloaded", u""),
        
        # Entry with plurals
        (_(u"In this message the proper way of translating plurals are seen. \
You need to enter between 1 and 6 different versions of the translation to \
ensure the correct grammar in your language. Read more about this here: \
http://translate.sourceforge.net/wiki/guide/translation/plurals"), 
        [u"%d file will be downloaded", u"%d files will be downloaded"], u""),
        
        (_(u"In this message, \"%s\" is a placeholder (variable) that \
represents a file name. Make sure your translation contains %s somewhere. When \
this message is used, the %s will be replaced with a file name e.g. 'The file \
will be saved as example.odt'.  Note that \"%s\" does not refer to a \
percentage."), 
        u"The file will be saved as %s", u""),
        
        (_(u"In this message the variable is surrounded by double quotes. Make \
sure your translation contains the variable %s and surround it similarly with \
quotes in the way required by your language. If your language uses the same \
quotes as English, type it exactly as shown for the English. If your language \
uses different characters you can just type them around the variable."), 
        u"The file \"%s\" was not saved", u""),
        
        (_(u"In this message, \"%(name)s\" is a placeholder (variable). Note \
that the 's' is part of the variable, and the whole variable from '%' to the \
's' should appear unchanged somewhere in your translation. These type of \
variables give you an idea of what they will contain. In this case, it will \
contain a name."), 
        u"Welcome back, %(name)s", u""),
        
        (_(u"In this message the user of the software is asked to do \
something. Make sure you translate it by being as polite or respectful as is \
necessary for your culture."), 
        u"Please enter your password here", u""),
        
        (_(u"In this message there is reference to \"Linux\" (a product name). \
Many languages will not translate it, but your language might use a \
transliteration if you don't use the Latin script for your language."), 
        u"This software runs on Linux", u""),
        
        (_(u"This message contains the URL (web address) of the project \
website. It must be transferred as a placeable or typed over exactly."), 
        u"Visit the project website at http://virtaal.org/", u""),
        
        (_(u"This message refers to a website with more information. Sometimes \
you might be allowed or encouraged to change the URL (web address) to a \
website in your language. In this case, replace the \"en\" at the start of the \
address to your language code so that the address points to the corresponding \
article in your language about XML."), 
        u"For more information about XML, visit \
http://en.wikipedia.org/wiki/XML", u""),
        
        # Entry with context message
        (_(u"This translation contains an ambiguous word - it has two possible \
meanings. Make sure you can see the context information showing that this is a \
verb (an action as in \"click here to view it\")."), 
        u"View", u"verb"),
        
        # Entry with context message
        (_(u"This translation contains an ambiguous word - it has two possible \
meanings. Make sure you can see the context information showing that this is a \
noun (a thing as in \"click to change the view to full screen\"). If Virtaal \
gives your previous translation as a suggestion, take care to only use it if \
it is definitely appropriate in this case as well."), 
        u"View", u"noun"),
        
        (_(u"An accelerator key is a key on your keyboard that you can press \
to quickly access a menu or function. It is also called a hot key, access key \
or mnemonic. In program interfaces they are shown as an underlined letter in \
the text label. In the translatable text they are marked using some character \
like the underscore here, but other characters are used for this as well. In \
this case the the accelerator key is \"f\" since the underscore is before this \
letter and it means that this accelerator could be triggered by pressing \
Alt+F."), 
        u"_File", u""),
        
        (_(u"In this entry you can see other kind of accelerator."), 
        u"&File", u""),
        
        (_(u"And another kind of accelerator."), 
        u"~File", u""),
        
        (_(u"Virtaal is able to provide suggestions from several terminology \
glossaries and provides easy shortcuts to allow paste them in the translation \
field. Right now Virtaal has only one empty terminology glossary, but you can \
start filling it. In order to do that select the original text, press Ctrl+T, \
provide a translation for your language, and save."), 
        u"Filter", u"verb"),
        
        (_(u"In the previous entry you have created one terminology entry for \
the \"filter\" verb. Now do the same for \"filter\" noun."), 
        u"Filter", u"noun"),
        
        (_(u"If you have created any terminology in the previous entries you \
may now see some of the words with a green background (or other color \
depending on your theme). This means that Virtaal has terminology suggestions \
for that word. Use Alt+Right to select the highlighted word, and then press \
Alt+Down. If only one suggestions is provided Alt+Down just copies the \
suggestion to the translation field. But if several suggestions are available \
Alt+Down shows a suggestion list which you can navigate using Down and Up \
keys. Once you have selected the desired suggestion press Enter to copy it to \
the translation field."), 
        u"Filter the list by date using the \"filter by date\" filter.", u""),
        
        (_(u"This message has two lines. Make sure that your translation also \
contains two lines. You can separate lines with Shift+Enter or copying \
new-line placeables (displayed as ¶)."), 
        u"A camera has been connected to your computer.\nNo photos were found \
on the camera.", u""),
        
        (_(u"This message contains tab characters to separate some headings. \
Make sure you separate your translations in the same way."), 
        u"Heading 1\tHeading 2\tHeading 3", u""),
        
        (_(u"This message contains a large number that is formatted according \
to American convention. Translate this but be sure to format the number \
according to the convention for your language. You might need to change the \
comma (,) and full stop (.) to other characters, and you might need to use a \
different number system. Make sure that you understand the American \
formatting: the number is bigger than one thousand."), 
        u"It will take 1,234.56 hours to do", u""),
        
        (_(u"This message refers to miles. If the programmers encourage it, \
you might want to change this to kilometres in your translation, if kilometres \
are more commonly used in your language. Note that 1 mile is about 1.6 \
kilometres. Note that automated tests for \"numbers\" will complain if the \
number is changed, but in this case it is safe to do."), 
        u"The road is 10 miles long", u""),
        
        (_(u"This message contains a link that the user will be able to click \
on to visit the help page. Make sure you maintain the information between the \
angle brackets (<...>) correctly. The double quotes (\") should never be \
changed in tags, even if your language uses a different type of quotation \
marks."), 
        u"Feel free to visit our <a href=\"http://translate.sourceforge.net/\">\
help page</a>", u""),
        
        (_(u"This message contains a similar link, but the programmers decided \
to rather insert the tags with variables so that translators can't change \
them. Make sure you position the two variables (%s) so that they correspond to \
the opening and closing tag of the previous translation."), 
        u"Feel free to visit our %shelp page%s", u""),
        
        (_(u"This message contains the <b> and </b> tags to emphasize a word, \
while everything is inside <p> and </p> tags. Make sure your whole translation \
is inside <p> and </p> tags."), 
        u"<p>Restart the program <b>now</b></p>", u""),
        
        (_(u"This message contains a similar link that is contained within \
<span> and </span>. Make sure you maintain all the tags (<...>) correctly, and \
that the link is contained completely inside the <span> and </span> tags in \
your translation. Make sure that the text inside the \"a\" tags correspond to \
\"help page\" and that your translation corresponding to the second sentence \
is contained in the <span> tags. Note how the full stop is still inside the \
</span> tag."), 
        u"The software has many features. <span class=\"info\">Feel free \
to visit our <a href=\"http://translate.sourceforge.net/\">help page</a>.\
</span>", u""),
        )
        
        # Tutorial filename at a temporary file in a random temporary directory
        from tempfile import mkdtemp
        filename = os.path.join(mkdtemp(), "virtaal_tutorial.pot")
        
        tutorial_file = factory.getobject(filename)
        for comment, source, context in entries:
            unit = tutorial_file.addsourceunit(source)# This creates an unit
            # with the provided source (even if plural) and returns it. In case
            # of plural, source should be a list of strings instead of a string
            if isinstance(source, list):# Maybe unnecessary since when Virtaal
                # opens the file and doesn't crash, even if it has only a
                # msgstr for plural entries, and it shows the appropiate number
                # of translation fields (for the target language)
                unit.settarget([u"", u""])
            unit.addnote(comment, "developer")
            unit.setcontext(context)
        tutorial_file.save()
        
        # Open the file just created on the fly
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

        if self.plugin_controller:
            self.plugin_controller.shutdown()
        self.emit('quit')
        self.view.quit()
        return False

    def run(self):
        self.view.show()
