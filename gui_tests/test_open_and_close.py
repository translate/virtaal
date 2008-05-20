#!/usr/bin/env python

from time import sleep
from os import path
import common

def create_ini_file(filename):
    return common.write_file(filename, """
[translator]
email = 
name = 
team = 

[undo]
depth = 50

[language]
uilang = af_ZA
contentlang = af_ZA
sourcelang = en

[general]
windowheight = 620
windowwidth = 400""")

def create_po_file(filename):
    return common.write_file(filename, """
#, fuzzy
msgid "Hello, world!"
msgstr "Hello, wereld!"
""")

def handle_popup_query(node, dialog_title, input_text):
    wnd = node.child(name=dialog_title)
    box = wnd.textentry(textEntryName="")
    box.typeText(input_text)
    ok_button = wnd.button(buttonName="OK")
    ok_button.click()

class TestOpenAndClose(common.LoadSaveTest):    
    def after_open(self, virtaal):
        edit_area = virtaal.child(roleName='table cell')
        sleep(1)
        edit_area.typeText("Hello, wereld!")
        edit_area.keyCombo("<Alt>u")

    def after_save(self, virtaal):
        handle_popup_query(virtaal, "Please enter your name", "Hello Person")
        handle_popup_query(virtaal, "Please enter your e-mail address", "hello@world.com")
        handle_popup_query(virtaal, "Please enter your team's information", "Hello Team")
        
    def test_open_and_close(self):
        po_file = create_po_file(self.abspath("hello_world.po"))
        self.load_save_test(create_ini_file(self.abspath("config.ini")), 
                            common.strip_translations(po_file), po_file)
