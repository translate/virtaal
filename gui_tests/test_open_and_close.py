#!/usr/bin/env python

from dogtail import tree, config
from dogtail.utils import run
from time import sleep
import os
from os import environ, path, remove

environ['LANGUAGE']='en_US.UTF-8'
config.config.defaults['absoluteNodePaths'] = True

os.chdir(path.dirname(__file__))

ini_file = open("test_open_and_close.ini", "w+")
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

def test_basic():    
    run("../run_virtaal.py --config=test_open_and_close.ini", timeout=0)
    
    if path.exists("hello_world.po"):
        os.unlink("hello_world.po")
    
    virtaal = tree.root.application("run_virtaal.py")
    
    menu_file = virtaal.menuItem("File")
    menu_open = menu_file.menuItem("Open")
    menu_open.click()
    
    dlg = virtaal.child(roleName="dialog")
    
    filename_box = dlg.child(label='Location:')
    filename_box.grabFocus()
    filename_box.keyCombo("BackSpace")
    filename_box.typeText("hello_world.pot")
    
    ok_button = dlg.child(roleName="push button", name="Open")
    ok_button.click()
    
    edit_area = virtaal.child(roleName='table cell')
    sleep(1)
    edit_area.typeText("Hello, wereld!")
    edit_area.keyCombo("<Alt>u")
    
    menu_open = menu_file.menuItem("Save As")
    menu_open.click()
    
    dlg = virtaal.child(roleName="dialog")
    
    filename_box = dlg.child(label='Name:')
    filename_box.grabFocus()
    filename_box.keyCombo("<Ctrl>a")
    filename_box.keyCombo("BackSpace")
    filename_box.typeText("hello_world.po")
    
    save_button = dlg.button(buttonName="Save")
    save_button.click()

    name_wnd = virtaal.child(name="Please enter your name")
    name_box = name_wnd.textentry(textEntryName="")
    name_box.typeText("Hello Person")
    ok_button = name_wnd.button(buttonName="OK")
    ok_button.click()
    
    email_wnd = virtaal.child(name="Please enter your e-mail address")
    email_box = email_wnd.textentry(textEntryName="")
    email_box.typeText("hello@world.com")
    ok_button = email_wnd.button(buttonName="OK")
    ok_button.click()
    
    team_wnd = virtaal.child(name="Please enter your team's information")
    team_box = team_wnd.textentry(textEntryName="")
    team_box.typeText("Hello Team")
    ok_button = team_wnd.button(buttonName="OK")
    ok_button.click()
    
    menu_open = menu_file.menuItem("Quit")
    sleep(1)
    menu_open.click()
    
    contents = open("hello_world.po").read().split("\n\n")
    assert contents[1] == '#, fuzzy\nmsgid "Hello, world!"\nmsgstr "Hello, wereld!"\n'
