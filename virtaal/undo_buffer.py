#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# VirTaal is free software; you can redistribute it and/or modify
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

"""This provides the data structure for keeping the undo data."""

import collections
import gtk

import pan_app
from support.partial import partial


class BoundedQueue(collections.deque):
    def __init__(self, get_size):
        super(BoundedQueue, self).__init__()
        self.current_pos = 0
        self.get_size = get_size

    def push(self, item):
        while len(self) > self.get_size():
            self.popleft()

        self.append(item)

def add_undo_to_buffer(buf):
    buf.__undo_stack = BoundedQueue(lambda: pan_app.settings.undo['depth'])

    buf.insert_handler = buf.connect("insert-text",  on_insert_text,  buf.__undo_stack)
    buf.delete_handler = buf.connect("delete-range", on_delete_range, buf.__undo_stack)

    return buf

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
        action = undo_list.pop()
        return action()
    return False

def on_delete_range(buf, start_iter, end_iter, undo_list):
    offset = start_iter.get_offset()
    text = buf.get_text(start_iter, end_iter)

    def undo():
        start_iter = buf.get_iter_at_offset(offset)
        execute_without_signals(buf, partial(buf.insert, start_iter, text))
        buf.place_cursor(start_iter)
        return True

    undo_list.push(undo)
    return True

def on_insert_text(buf, iter, text, length, undo_list):
    offset = iter.get_offset()

    def undo():
        start_iter = buf.get_iter_at_offset(offset)
        end_iter = buf.get_iter_at_offset(offset + length)
        execute_without_signals(buf, partial(buf.delete, start_iter, end_iter))
        buf.place_cursor(start_iter)
        return True

    undo_list.push(undo)
    return True

