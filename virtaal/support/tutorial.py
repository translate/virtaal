#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 Zuza Software Foundation
# Copyright 2012 Leandro Regueiro Iglesias
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

import os.path
from tempfile import mkdtemp

from translate.storage import factory


def create_localized_tutorial():
    """Save on disk a tutorial POT file with comments using current locale."""

    # All the entries in the tutorial.
    #
    # It is a tuple of entries, in which entry is in the form of a tuple with a
    # comment for the translator, a string (or list of source strings) and an
    # optional string context (blank string if not provided).
    tutorial_entries = (
    # Translators: Don't translate the "Welcome" word.
    (_(u"Welcome to the Virtaal tutorial. You can do the first translation by "
       u"typing just the translation for \"Welcome\". Then press Enter."),
     u"Welcome",
     u""),

    (_(u"Translate this slightly longer message. If a spell checker is "
       u"available, spelling mistakes are indicated similarly to word "
       u"processors. Make sure the correct language is selected in the bottom "
       u"right of the window."),
     u"With this file you can learn about translation using Virtaal",
     u""),

    (_(u"This tutorial will show you some of the things you might want to pay "
       u"attention to while translating software programs. It will help you "
       u"to avoid some problems and produce translations of a higher "
       u"quality."),
     u"Quality is important",
     u""),

    (_(u"Some of the advice will only be relevant to some languages. For "
       u"example, if your language does not use the Latin alphabet, some of "
       u"the advice might not be relevant to translation in your language. "
       u"For many languages there are established translation rules."),
     u"Languages are different",
     u""),

    (_(u"The correct use of capital letters are important in many languages. "
       u"Translate this message with careful attention to write \"Virtaal\" "
       u"with a capital letter."),
     u"The product we use is called Virtaal",
     u""),

    (_(u"In this message the English uses a capital letter for almost every "
       u"word. Almost no other language uses this style. Unless your language "
       u"definitely needs to follow the English style (also called Title "
       u"Case), translate this by following the normal capitalisation rules "
       u"for your language. If your language does not use capital letters, "
       u"simply translate it normally."),
     u"Download the File Now",
     u""),

    (_(u"If you translated the previous message you should see a window with "
       u"that translation and a percentage indicating how similar the source "
       u"strings (English) are. It is Virtaal's translation memory at work. "
       u"Press Ctrl+1 to copy the suggested translation to the current "
       u"translation. Remember to always review suggestions before you use "
       u"them."),
     u"Download the files now",
     u""),

    (_(u"This is a simple message that starts with a capital letter in "
       u"English. If your language uses capital letters, you almost "
       u"definitely want to start your translation with a capital letter as "
       u"well."),
     u"Time",
     u""),

    (_(u"This is a simple message that starts with a lower case letter in "
       u"English. If your language uses capital letters, you almost "
       u"definitely want to start your translation with a lower case letter "
       u"as well."),
     u"later",
     u""),

    (_(u"This message is a question. Make sure that you use the correct "
       u"question mark in your translation as well."),
     u"What is your name?",
     u""),

    (_(u"This message is a label as part of a form. Note how it ends with a "
       u"colon (:)."),
     u"Name:",
     u""),

    (_(u"If the source will remain mostly or completely unchanged it is "
       u"convenient to copy the entire source string with Alt+Down. Here is "
       u"almost nothing to translate, so just press Alt+Down and make "
       u"corrections if necessary."),
     u"<b><a href=\"http://virtaal.org/\">Virtaal</a></b>",
     u""),

    (_(u"Placeables are special parts of the text, like the © symbol, that "
       u"can be automatically highlighted and easily inserted into the "
       u"translation. Select the © with Alt+Right and transfer it to the "
       u"target with Alt+Down."),
     u"© Virtaal Team",
     u""),

    (_(u"Recognised placeables include special symbols, numbers, variable "
       u"placeholders, acronyms and many more. Move to each one with "
       u"Alt+Right and transfer it down with Alt+Down."),
     u"© 2009 contributors",
     u""),

    (_(u"This message ends with ... to indicate that clicking on this text "
       u"will cause a dialogue to appear instead of just performing an "
       u"action. Be sure to end your message with ... as well."),
     u"Save As...",
     u""),

    (_(u"This message ends with a special character that looks like three "
       u"dots. Select the special character with Alt+Right and copy it to "
       u"your translation with Alt+Down. Don't just type three dot "
       u"characters."),
     u"Save As…",
     u""),

    (_(u"This message has two sentences. Translate them and make sure you "
       u"start each with a capital letter if your language uses them, and end "
       u"each sentence properly."),
     u"Always try your best. Many people are available to learn from.",
     u""),

    (_(u"This message marks the word \"now\" as important with bold tags. "
       u"These tags can be transferred from the source with Alt+Right and "
       u"Alt+Down. Leave the <b> and </b> in the translation around the part "
       u"that corresponds to \"now\". Read more about XML markup here: "
       u"http://en.wikipedia.org/wiki/XML"),
     u"Restart the program <b>now</b>",
     u""),

    (_(u"This message is very similar to the previous message. Use the "
       u"suggestion of the previous translation with Ctrl+1. Note how the "
       u"only difference is that this one ends with a full stop after the "
       u"last tag."),
     u"Restart the program <b>now</b>.",
     u""),

    (_(u"In this message \"%d\" is a placeholder (variable) that represents a "
       u"number. Make sure your translation contains \"%d\" somewhere. In "
       u"this case it refers a number of files. When this message is used the "
       u"\"%d\" will be replaced with a number e.g. 'Number of files copied: "
       u"5'.  Note that \"%d\" does not refer to a percentage."),
     u"Number of files copied: %d",
     u""),

    (_(u"In this message, \"%d\" refers again to the number of files, but "
       u"note how the \"(s)\" is used to show that we don't know how many it "
       u"will be. This is often hard to translate well. If you encounter this "
       u"in software translation, you might want to hear from developers if "
       u"this can be avoided. Read more about this and decide how to do it in "
       u"your language: http://docs.translatehouse.org/projects/"
       u"localization-guide/en/latest/guide/translation/plurals.html"),
     u"%d file(s) will be downloaded",
     u""),

    # Entry with plurals.
    (_(u"In this message the proper way of translating plurals are seen. You "
       u"need to enter between 1 and 6 different versions of the translation "
       u"to ensure the correct grammar in your language. Read more about this "
       u"here: http://docs.translatehouse.org/projects/localization-guide/en/"
       u"latest/guide/translation/plurals.html"),
     [
        u"%d file will be downloaded",
        u"%d files will be downloaded",
     ],
     u""),

    (_(u"In this message, \"%s\" is a placeholder (variable) that represents "
       u"a file name. Make sure your translation contains %s somewhere. When "
       u"this message is used, the %s will be replaced with a file name e.g. "
       u"'The file will be saved as example.odt'.  Note that \"%s\" does not "
       u"refer to a percentage."),
     u"The file will be saved as %s",
     u""),

    (_(u"In this message the variable is surrounded by double quotes. Make "
       u"sure your translation contains the variable %s and surround it "
       u"similarly with quotes in the way required by your language. If your "
       u"language uses the same quotes as English, type it exactly as shown "
       u"for the English. If your language uses different quoting characters "
       u"you can just type them around the variable."),
     u"The file \"%s\" was not saved",
     u""),

    (_(u"In this message, \"%(name)s\" is a placeholder (variable). Note that "
       u"the 's' is part of the variable, and the whole variable from '%' to "
       u"the 's' should appear unchanged somewhere in your translation. These "
       u"type of variables give you an idea of what they will contain. In "
       u"this case, it will contain a name."),
     u"Welcome back, %(name)s",
     u""),

    (_(u"In this message the user of the software is asked to do something. "
       u"Make sure you translate it by being as polite or respectful as is "
       u"necessary for your culture."),
     u"Please enter your password here",
     u""),

    (_(u"In this message there is reference to \"Linux\" (a product name). "
       u"Many languages will not translate it, but your language might use a "
       u"transliteration if you don't use the Latin script for your "
       u"language."),
     u"This software runs on Linux",
     u""),

    (_(u"This message contains the URL (web address) of the project website. "
       u"It must be transferred as a placeable or typed over exactly."),
     u"Visit the project website at http://virtaal.org/",
     u""),

    (_(u"This message refers to a website with more information. Sometimes "
       u"you might be allowed or encouraged to change the URL (web address) "
       u"to a website in your language. In this case, replace the \"en\" at "
       u"the start of the address to your language code so that the address "
       u"points to the corresponding article in your language about XML."),
     u"For more information about XML, visit http://en.wikipedia.org/wiki/XML",
     u""),

    # Entry with context message.
    (_(u"This translation contains an ambiguous word - it has two possible "
       u"meanings. Make sure you can see the context information showing that "
       u"this is a verb (an action as in \"click here to view it\")."),
     u"View",
     u"verb"),

    # Entry with context message.
    (_(u"This translation contains an ambiguous word - it has two possible "
       u"meanings. Make sure you can see the context information showing that "
       u"this is a noun (a thing as in \"click to change the view to full "
       u"screen\"). If Virtaal gives your previous translation as a "
       u"suggestion, take care to only use it if it is definitely appropriate "
       u"in this case as well."),
     u"View",
     u"noun"),

    (_(u"An accelerator key is a key on your keyboard that you can press to "
       u"quickly access a menu or function. It is also called a hot key, "
       u"access key or mnemonic. In program interfaces they are shown as an "
       u"underlined letter in the text label. In the translatable text they "
       u"are marked using some character like the underscore here, but other "
       u"characters are used for this as well. In this case the the "
       u"accelerator key is \"f\" since the underscore is before this letter "
       u"and it means that this accelerator could be triggered by pressing "
       u"Alt+F."),
     u"_File",
     u""),

    (_(u"In this entry you can see other kind of accelerator."),
     u"&File",
     u""),

    (_(u"And another kind of accelerator."),
     u"~File",
     u""),

    # Entry with context message.
    (_(u"You can maintain a local terminology file to help you translate "
       u"consistently. To add a term, select a word (or words), press Ctrl+T "
       u"and fill in the details for the new term. Select the text below and "
       u"add a term for it."),
     u"Filter",
     u"verb"),

    # Entry with context message.
    (_(u"In the previous entry you have created one terminology entry for the "
       u"\"filter\" verb. Now do the same for \"filter\" noun."),
     u"Filter",
     u"noun"),

    (_(u"If you have created any terminology in the previous entries you may "
       u"now see some of the words with a green background (or other color "
       u"depending on your theme). This means that Virtaal has terminology "
       u"suggestions for that word. Use Alt+Right to select the highlighted "
       u"word, and then press Alt+Down. If only one suggestion is provided "
       u"then Alt+Down just copies the suggestion to the translation field. "
       u"But if several suggestions are available Alt+Down shows a suggestion "
       u"list which you can navigate using Down and Up keys. Once you have "
       u"selected the desired suggestion press Enter to copy it to the "
       u"translation field."),
     u"Filter the list by date using the \"filter by date\" filter.",
     u""),

    (_(u"This message has two lines. Make sure that your translation also "
       u"contains two lines. You can separate lines with Shift+Enter or copy "
       u"newline placeables (displayed as ¶)."),
     (u"A camera has been connected to your computer.\nNo photos were found "
      u"on the camera."),
     u""),

    (_(u"This message contains tab characters to separate some headings. Make "
       u"sure you separate your translations in the same way."),
     u"Heading 1\tHeading 2\tHeading 3",
     u""),

    (_(u"This message contains a large number that is formatted according to "
       u"the American convention. Translate this but make sure to format the "
       u"number according to your language's convention. You might need to "
       u"change the comma (,) and full stop (.) to other characters, and you "
       u"also might need to use a different number system. Make sure that you "
       u"understand the American formatting: this number is bigger than one "
       u"thousand."),
     u"It will take 1,234.56 hours to do",
     u""),

    (_(u"This message refers to miles. If the programmers encourage it, you "
       u"might want to change this to kilometres in your translation, if "
       u"kilometers are more commonly used in your language. Note that 1 mile "
       u"is about 1.6 kilometres. Note that automated tests for \"numbers\" "
       u"will complain if the number is changed, but in this case it is safe "
       u"to do so."),
     u"The road is 10 miles long",
     u""),

    (_(u"This message contains a link that the user will be able to click on "
       u"to visit the help page. Make sure you correctly keep the information "
       u"between the angle brackets (<...>). The double quotes (\") should "
       u"never be changed in tags, even if your language uses a different "
       u"type of quotation marks."),
     (u"Feel free to visit our <a "
      u"href=\"http://docs.translatehouse.org/projects/virtaal/en/latest/\">"
      u"help page</a>"),
     u""),

    (_(u"This message contains a similar link, but the programmers decided to "
       u"rather insert the tags by using variables so that translators can't "
       u"change them. Make sure you position the two variables (%s) so that "
       u"they correspond to the opening and closing tags of the previous "
       u"translation."),
     u"Feel free to visit our %shelp page%s",
     u""),

    (_(u"This message contains the <b> and </b> tags to emphasize a word, "
       u"while everything is within the <p> and </p> tags. Make sure your "
       u"whole translation is within the <p> and </p> tags."),
     u"<p>Restart the program <b>now</b></p>",
     u""),

    (_(u"This message contains a similar link that is contained within <span> "
       u"and </span>. Make sure you correctly keep all the tags (<...>), and "
       u"that the link is completely contained within the <span> and </span> "
       u"tags in your translation. Make sure that the text inside the "
       u"\"a\" tags correspond to \"help page\" and that your translation "
       u"corresponding to the second sentence is contained in the <span> "
       u"tags. Note how the full stop is still inside the </span> tag."),
     (u"The software has many features. <span class=\"info\">Feel free to "
      u"to visit our <a "
      u"href=\"http://docs.translatehouse.org/projects/virtaal/en/latest/\">"
      u"help page</a>.</span>"),
     u""),
    )

    # Tutorial filename at a temporary file in a random temporary directory.
    filename = os.path.join(mkdtemp("", "tmp_virtaal_"), "virtaal_tutorial.pot")

    tutorial_file = factory.getobject(filename)

    for comment, source, context in tutorial_entries:
        # The next creates an unit with the provided source (even if plural)
        # and returns it. In case of plural, source should be a list of strings
        # instead of a string.
        unit = tutorial_file.addsourceunit(source)

        if isinstance(source, list):
            # Maybe unnecessary since when Virtaal opens the file and doesn't
            # crash, even if it has only a msgstr for plural entries, and it
            # shows the appropiate number of translation fields (for the target
            # language).
            unit.settarget([u"", u""])

        unit.addnote(comment, "developer")
        unit.setcontext(context)

    tutorial_file.save()

    # Return the filename to enable opening the file.
    return filename
