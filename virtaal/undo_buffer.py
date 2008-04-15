#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2008 Zuza Software Foundation
# 
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import collections
import gtk

import Globals


class BoundedQueue(collections.deque):
    def __init__(self, get_size):
        self.current_pos = 0
        self.get_size = get_size
    
        
    def enqueue(self, item):
        while len(self) > self.get_size():
            self.dequeue()
            
        self.append(item)
        
    
    def dequeue(self):
        return self.popleft()


def make_undo_buffer():
    buffer = gtk.TextBuffer()
    undo_list = BoundedQueue(lambda: Globals.settings.undo['depth'])
    
    buffer.insert_handler = buffer.connect("insert-text",       on_insert_text,       undo_list)
    buffer.delete_handler = buffer.connect("delete-range",      on_delete_range,      undo_list)
    
    return buffer, undo_list
    

def block_change_signals(self):
    self.handler_block(self.insert_handler)
    self.handler_block(self.delete_handler)


def unblock_change_signals(self):
    self.handler_unblock(self.insert_handler)
    self.handler_unblock(self.delete_handler)


def execute_without_signals(self, action):
    block_change_signals(self)
    result = action()
    unblock_change_signals(self)
    
    return result


def undo(undo_list):
    if len(undo_list) > 0:
        action = undo_list.dequeue()
        return action()
    
    return False
    
       
def on_delete_range(buffer, start_iter, end_iter, undo_list):
    text = buffer.get_text(start_iter, end_iter)
    start_mark = buffer.create_mark(None, start_iter, False) 

    def undo():
        execute_without_signals(buffer, lambda: buffer.insert(buffer.get_iter_at_mark(start_mark), text))
        buffer.delete_mark(start_mark)
        
        return True
    
    undo_list.enqueue(undo)    
    
    return True
    
    
def on_insert_text(buffer, iter, text, length, undo_list):
    start_mark = buffer.create_mark(None, iter, left_gravity=True)
    
    def undo():
        start_iter = buffer.get_iter_at_mark(start_mark)
        
        end_iter   = start_iter.copy()
        end_iter.forward_chars(length)
        
        execute_without_signals(buffer, lambda: buffer.delete(start_iter, end_iter))
        buffer.delete_mark(start_mark)
        
        return True

    undo_list.enqueue(undo)
    
    return True

  