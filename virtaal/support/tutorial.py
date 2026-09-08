#!/usr/bin/env python
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
    (_("Welcome to the Virtaal tutorial. You can do the first translation by "
       "typing just the translation for \"Welcome\". Then press Enter."),
     "Welcome",
     ""),

    (_("Translate this slightly longer message. If a spell checker is "
       "available, spelling mistakes are indicated similarly to word "
       "processors. Make sure the correct language is selected in the bottom "
       "right of the window."),
     "With this file you can learn about translation using Virtaal",
     ""),

    (_("This tutorial will show you some of the things you might want to pay "
       "attention to while translating software programs. It will help you "
       "to avoid some problems and produce translations of a higher "
       "quality."),
     "Quality is important",
     ""),

    (_("Some of the advice will only be relevant to some languages. For "
       "example, if your language does not use the Latin alphabet, some of "
       "the advice might not be relevant to translation in your language. "
       "For many languages there are established translation rules."),
     "Languages are different",
     ""),

    (_("The correct use of capital letters are important in many languages. "
       "Translate this message with careful attention to write \"Virtaal\" "
       "with a capital letter."),
     "The product we use is called Virtaal",
     ""),

    (_("In this message the English uses a capital letter for almost every "
       "word. Almost no other language uses this style. Unless your language "
       "definitely needs to follow the English style (also called Title "
       "Case), translate this by following the normal capitalisation rules "
       "for your language. If your language does not use capital letters, "
       "simply translate it normally."),
     "Download the File Now",
     ""),

    (_("If you translated the previous message you should see a window with "
       "that translation and a percentage indicating how similar the source "
       "strings (English) are. It is Virtaal's translation memory at work. "
       "Press Ctrl+1 to copy the suggested translation to the current "
       "translation. Remember to always review suggestions before you use "
       "them."),
     "Download the files now",
     ""),

    (_("This is a simple message that starts with a capital letter in "
       "English. If your language uses capital letters, you almost "
       "definitely want to start your translation with a capital letter as "
       "well."),
     "Time",
     ""),

    (_("This is a simple message that starts with a lower case letter in "
       "English. If your language uses capital letters, you almost "
       "definitely want to start your translation with a lower case letter "
       "as well."),
     "later",
     ""),

    (_("This message is a question. Make sure that you use the correct "
       "question mark in your translation as well."),
     "What is your name?",
     ""),

    (_("This message is a label as part of a form. Note how it ends with a "
       "colon (:)."),
     "Name:",
     ""),

    (_("If the source will remain mostly or completely unchanged it is "
       "convenient to copy the entire source string with Alt+Down. Here is "
       "almost nothing to translate, so just press Alt+Down and make "
       "corrections if necessary."),
     "<b><a href=\"http://virtaal.org/\">Virtaal</a></b>",
     ""),

    (_("Placeables are special parts of the text, like the © symbol, that "
       "can be automatically highlighted and easily inserted into the "
       "translation. Select the © with Alt+Right and transfer it to the "
       "target with Alt+Down."),
     "© Virtaal Team",
     ""),

    (_("Recognised placeables include special symbols, numbers, variable "
       "placeholders, acronyms and many more. Move to each one with "
       "Alt+Right and transfer it down with Alt+Down."),
     "© 2009 contributors",
     ""),

    (_("This message ends with ... to indicate that clicking on this text "
       "will cause a dialogue to appear instead of just performing an "
       "action. Be sure to end your message with ... as well."),
     "Save As...",
     ""),

    (_("This message ends with a special character that looks like three "
       "dots. Select the special character with Alt+Right and copy it to "
       "your translation with Alt+Down. Don't just type three dot "
       "characters."),
     "Save As…",
     ""),

    (_("This message has two sentences. Translate them and make sure you "
       "start each with a capital letter if your language uses them, and end "
       "each sentence properly."),
     "Always try your best. Many people are available to learn from.",
     ""),

    (_("This message marks the word \"now\" as important with bold tags. "
       "These tags can be transferred from the source with Alt+Right and "
       "Alt+Down. Leave the <b> and </b> in the translation around the part "
       "that corresponds to \"now\". Read more about XML markup here: "
       "http://en.wikipedia.org/wiki/XML"),
     "Restart the program <b>now</b>",
     ""),

    (_("This message is very similar to the previous message. Use the "
       "suggestion of the previous translation with Ctrl+1. Note how the "
       "only difference is that this one ends with a full stop after the "
       "last tag."),
     "Restart the program <b>now</b>.",
     ""),

    (_("In this message \"%d\" is a placeholder (variable) that represents a "
       "number. Make sure your translation contains \"%d\" somewhere. In "
       "this case it refers a number of files. When this message is used the "
       "\"%d\" will be replaced with a number e.g. 'Number of files copied: "
       "5'.  Note that \"%d\" does not refer to a percentage."),
     "Number of files copied: %d",
     ""),

    (_("In this message, \"%d\" refers again to the number of files, but "
       "note how the \"(s)\" is used to show that we don't know how many it "
       "will be. This is often hard to translate well. If you encounter this "
       "in software translation, you might want to hear from developers if "
       "this can be avoided. Read more about this and decide how to do it in "
       "your language: http://docs.translatehouse.org/projects/"
       "localization-guide/en/latest/guide/translation/plurals.html"),
     "%d file(s) will be downloaded",
     ""),

    # Entry with plurals.
    (_("In this message the proper way of translating plurals are seen. You "
       "need to enter between 1 and 6 different versions of the translation "
       "to ensure the correct grammar in your language. Read more about this "
       "here: http://docs.translatehouse.org/projects/localization-guide/en/"
       "latest/guide/translation/plurals.html"),
     [
        "%d file will be downloaded",
        "%d files will be downloaded",
     ],
     ""),

    (_("In this message, \"%s\" is a placeholder (variable) that represents "
       "a file name. Make sure your translation contains %s somewhere. When "
       "this message is used, the %s will be replaced with a file name e.g. "
       "'The file will be saved as example.odt'.  Note that \"%s\" does not "
       "refer to a percentage."),
     "The file will be saved as %s",
     ""),

    (_("In this message the variable is surrounded by double quotes. Make "
       "sure your translation contains the variable %s and surround it "
       "similarly with quotes in the way required by your language. If your "
       "language uses the same quotes as English, type it exactly as shown "
       "for the English. If your language uses different quoting characters "
       "you can just type them around the variable."),
     "The file \"%s\" was not saved",
     ""),

    (_("In this message, \"%(name)s\" is a placeholder (variable). Note that "
       "the 's' is part of the variable, and the whole variable from '%' to "
       "the 's' should appear unchanged somewhere in your translation. These "
       "type of variables give you an idea of what they will contain. In "
       "this case, it will contain a name."),
     "Welcome back, %(name)s",
     ""),

    (_("In this message the user of the software is asked to do something. "
       "Make sure you translate it by being as polite or respectful as is "
       "necessary for your culture."),
     "Please enter your password here",
     ""),

    (_("In this message there is reference to \"Linux\" (a product name). "
       "Many languages will not translate it, but your language might use a "
       "transliteration if you don't use the Latin script for your "
       "language."),
     "This software runs on Linux",
     ""),

    (_("This message contains the URL (web address) of the project website. "
       "It must be transferred as a placeable or typed over exactly."),
     "Visit the project website at http://virtaal.org/",
     ""),

    (_("This message refers to a website with more information. Sometimes "
       "you might be allowed or encouraged to change the URL (web address) "
       "to a website in your language. In this case, replace the \"en\" at "
       "the start of the address to your language code so that the address "
       "points to the corresponding article in your language about XML."),
     "For more information about XML, visit http://en.wikipedia.org/wiki/XML",
     ""),

    # Entry with context message.
    (_("This translation contains an ambiguous word - it has two possible "
       "meanings. Make sure you can see the context information showing that "
       "this is a verb (an action as in \"click here to view it\")."),
     "View",
     "verb"),

    # Entry with context message.
    (_("This translation contains an ambiguous word - it has two possible "
       "meanings. Make sure you can see the context information showing that "
       "this is a noun (a thing as in \"click to change the view to full "
       "screen\"). If Virtaal gives your previous translation as a "
       "suggestion, take care to only use it if it is definitely appropriate "
       "in this case as well."),
     "View",
     "noun"),

    (_("An accelerator key is a key on your keyboard that you can press to "
       "quickly access a menu or function. It is also called a hot key, "
       "access key or mnemonic. In program interfaces they are shown as an "
       "underlined letter in the text label. In the translatable text they "
       "are marked using some character like the underscore here, but other "
       "characters are used for this as well. In this case the "
       "accelerator key is \"f\" since the underscore is before this letter "
       "and it means that this accelerator could be triggered by pressing "
       "Alt+F."),
     "_File",
     ""),

    (_("In this entry you can see other kind of accelerator."),
     "&File",
     ""),

    (_("And another kind of accelerator."),
     "~File",
     ""),

    # Entry with context message.
    (_("You can maintain a local terminology file to help you translate "
       "consistently. To add a term, select a word (or words), press Ctrl+T "
       "and fill in the details for the new term. Select the text below and "
       "add a term for it."),
     "Filter",
     "verb"),

    # Entry with context message.
    (_("In the previous entry you have created one terminology entry for the "
       "\"filter\" verb. Now do the same for \"filter\" noun."),
     "Filter",
     "noun"),

    (_("If you have created any terminology in the previous entries you may "
       "now see some of the words with a green background (or other color "
       "depending on your theme). This means that Virtaal has terminology "
       "suggestions for that word. Use Alt+Right to select the highlighted "
       "word, and then press Alt+Down. If only one suggestion is provided "
       "then Alt+Down just copies the suggestion to the translation field. "
       "But if several suggestions are available Alt+Down shows a suggestion "
       "list which you can navigate using Down and Up keys. Once you have "
       "selected the desired suggestion press Enter to copy it to the "
       "translation field."),
     "Filter the list by date using the \"filter by date\" filter.",
     ""),

    (_("This message has two lines. Make sure that your translation also "
       "contains two lines. You can separate lines with Shift+Enter or copy "
       "newline placeables (displayed as ¶)."),
     ("A camera has been connected to your computer.\nNo photos were found "
      "on the camera."),
     ""),

    (_("This message contains tab characters to separate some headings. Make "
       "sure you separate your translations in the same way."),
     "Heading 1\tHeading 2\tHeading 3",
     ""),

    (_("This message contains a large number that is formatted according to "
       "the American convention. Translate this but make sure to format the "
       "number according to your language's convention. You might need to "
       "change the comma (,) and full stop (.) to other characters, and you "
       "also might need to use a different number system. Make sure that you "
       "understand the American formatting: this number is bigger than one "
       "thousand."),
     "It will take 1,234.56 hours to do",
     ""),

    (_("This message refers to miles. If the programmers encourage it, you "
       "might want to change this to kilometres in your translation, if "
       "kilometers are more commonly used in your language. Note that 1 mile "
       "is about 1.6 kilometres. Note that automated tests for \"numbers\" "
       "will complain if the number is changed, but in this case it is safe "
       "to do so."),
     "The road is 10 miles long",
     ""),

    (_("This message contains a link that the user will be able to click on "
       "to visit the help page. Make sure you correctly keep the information "
       "between the angle brackets (<...>). The double quotes (\") should "
       "never be changed in tags, even if your language uses a different "
       "type of quotation marks."),
     ("Feel free to visit our <a "
      "href=\"http://docs.translatehouse.org/projects/virtaal/en/latest/\">"
      "help page</a>"),
     ""),

    (_("This message contains a similar link, but the programmers decided to "
       "rather insert the tags by using variables so that translators can't "
       "change them. Make sure you position the two variables (%s) so that "
       "they correspond to the opening and closing tags of the previous "
       "translation."),
     "Feel free to visit our %shelp page%s",
     ""),

    (_("This message contains the <b> and </b> tags to emphasize a word, "
       "while everything is within the <p> and </p> tags. Make sure your "
       "whole translation is within the <p> and </p> tags."),
     "<p>Restart the program <b>now</b></p>",
     ""),

    (_("This message contains a similar link that is contained within <span> "
       "and </span>. Make sure you correctly keep all the tags (<...>), and "
       "that the link is completely contained within the <span> and </span> "
       "tags in your translation. Make sure that the text inside the "
       "\"a\" tags correspond to \"help page\" and that your translation "
       "corresponding to the second sentence is contained in the <span> "
       "tags. Note how the full stop is still inside the </span> tag."),
     ("The software has many features. <span class=\"info\">Feel free to "
      "to visit our <a "
      "href=\"http://docs.translatehouse.org/projects/virtaal/en/latest/\">"
      "help page</a>.</span>"),
     ""),
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
            # shows the appropriate number of translation fields (for the target
            # language).
            unit.target = ["", ""]

        unit.addnote(comment, "developer")
        unit.setcontext(context)

    tutorial_file.save()

    # Return the filename to enable opening the file.
    return filename
