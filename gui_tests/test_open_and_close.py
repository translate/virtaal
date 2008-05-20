#!/usr/bin/env python

from time import sleep
import os
from os import path
import common

def create_ini_file(filename):
    ini_file = open(path.abspath(filename), "w+")
    ini_file.write("""
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
windowwidth = 400
    """)
    ini_file.close()

def handle_popup_query(node, dialog_title, input_text):
    wnd = node.child(name=dialog_title)
    box = wnd.textentry(textEntryName="")
    box.typeText(input_text)
    ok_button = wnd.button(buttonName="OK")
    ok_button.click()

def test_basic():
    os.chdir(path.dirname(__file__))
    
    if path.exists("hello_world.po"):
        os.unlink("hello_world.po")

    create_ini_file("test_open_and_close.ini")
    virtaal = common.run_virtaal("test_open_and_close.ini")
    common.gui_openfile(virtaal, "hello_world.pot")
    
    edit_area = virtaal.child(roleName='table cell')
    sleep(1)
    edit_area.typeText("Hello, wereld!")
    edit_area.keyCombo("<Alt>u")
        
    common.gui_saveas(virtaal, "hello_world.po")
    handle_popup_query(virtaal, "Please enter your name", "Hello Person")
    handle_popup_query(virtaal, "Please enter your e-mail address", "hello@world.com")
    handle_popup_query(virtaal, "Please enter your team's information", "Hello Team")
    
    common.gui_quit(virtaal)
    
    contents = open("hello_world.po").read().split("\n\n")
    assert contents[1] == '#, fuzzy\nmsgid "Hello, world!"\nmsgstr "Hello, wereld!"\n'
