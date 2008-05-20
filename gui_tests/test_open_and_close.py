#!/usr/bin/env python

from time import sleep
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

class TestOpenAndClose(common.BaseGuiTest):
    def test_open_and_close(self):
        CONFIG_FILE = self.abspath("config.ini")
        PO_FILE = self.abspath("hello_world.po")
        TEST_PO_FILE = self.abspath("test_hello_world.po")

        virtaal = self.run(config=create_ini_file(CONFIG_FILE))
                
        po_file = create_po_file(PO_FILE)
        common.gui_openfile(virtaal, common.strip_translations(po_file))
        
        edit_area = virtaal.child(roleName='table cell')
        sleep(1)
        edit_area.typeText("Hello, wereld!")
        edit_area.keyCombo("<Alt>u")
        
        common.gui_saveas(virtaal, TEST_PO_FILE)
        handle_popup_query(virtaal, "Please enter your name", "Hello Person")
        handle_popup_query(virtaal, "Please enter your e-mail address", "hello@world.com")
        handle_popup_query(virtaal, "Please enter your team's information", "Hello Team")
        
        common.gui_quit(virtaal)
    
        print common.read_file(TEST_PO_FILE)
    
#    contents = open("hello_world.po").read().split("\n\n")
#    assert contents[1] == '#, fuzzy\nmsgid "Hello, world!"\nmsgstr "Hello, wereld!"\n'
