#!/usr/bin/env python

from dogtail import tree
from dogtail.utils import run
from time import sleep
import os
from os import environ, path, remove
environ['LANG']='en_US.UTF-8'

run("../run_virtaal.py --no_config", timeout=0)

if path.exists("hello_world.po"):
    os.unlink("hello_world.po")

virtaal = tree.root.application("run_virtaal.py")

menu_file = virtaal.menuItem("File")
menu_open = menu_file.menuItem("Open")
menu_open.click()
dlg = virtaal.child(roleName="dialog")
