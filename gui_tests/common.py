import os
from os import path, environ

from dogtail import tree, config
from dogtail.utils import run

environ['LANGUAGE']='en_US.UTF-8'
config.config.defaults['absoluteNodePaths'] = True

def run_virtaal(config_file):
    run("../run_virtaal.py --config=%s" % path.abspath(config_file), timeout=0)
    return tree.root.application("run_virtaal.py")

def click_file_open(node):
    node.menuItem("File").menuItem("Open").click()
    return node.child(roleName="dialog")

def gui_openfile(node, filename):
    dlg = click_file_open(node)
    
    filename_box = dlg.child(label='Location:')
    filename_box.grabFocus()
    filename_box.keyCombo("BackSpace")
    filename_box.typeText(filename)
    
    ok_button = dlg.child(roleName="push button", name="Open")
    ok_button.click()

def click_file_saveas(node):
    node.menuItem("File").menuItem("Save As").click()
    return node.child(roleName="dialog")

def gui_saveas(node, filename):
    dlg = click_file_saveas(node)

    filename_box = dlg.child(label='Name:')
    filename_box.grabFocus()
    filename_box.keyCombo("<Ctrl>a")
    filename_box.keyCombo("BackSpace")
    filename_box.typeText(filename)
    
    save_button = dlg.button(buttonName="Save")
    save_button.click()

def gui_quit(node):
    node.menuItem("File").menuItem("Quit").click()
