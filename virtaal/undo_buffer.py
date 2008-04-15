import gtk


def make_undo_buffer():
    buffer = gtk.TextBuffer()
    undo_list = []
    
    #buffer.connect("begin-user-action", on_begin_user_action, undo_list)
    buffer.insert_handler = buffer.connect("insert-text",       on_insert_text,       undo_list)
    buffer.delete_handler = buffer.connect("delete-range",      on_delete_range,      undo_list)
    #buffer.connect("end-user-action",   on_end_user_action,   undo_list)
    
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


#def on_begin_user_action(textbuffer, undo_list):
#    del undo_list[:]
#    return True


def undo(undo_list):
    if len(undo_list) > 0:
        action = undo_list.pop()
        return action()
    
    return False
    
       
def on_delete_range(buffer, start_iter, end_iter, undo_list):
    text = buffer.get_text(start_iter, end_iter)
    start_mark = buffer.create_mark(None, start_iter, False) 

    def undo():
        execute_without_signals(buffer, lambda: buffer.insert(buffer.get_iter_at_mark(start_mark), text))
        buffer.delete_mark(start_mark)
        
        return True
    
    undo_list.append(undo)    
    
    return True
    
    
#def on_end_user_action(textbuffer, undo_list):
#    return True

  
def on_insert_text(buffer, iter, text, length, undo_list):
    start_mark = buffer.create_mark(None, iter, left_gravity=True)
    
    def undo():
        start_iter = buffer.get_iter_at_mark(start_mark)
        
        end_iter   = start_iter.copy()
        end_iter.forward_chars(length)
        
        execute_without_signals(buffer, lambda: buffer.delete(start_iter, end_iter))
        buffer.delete_mark(start_mark)
        #buffer.delete_mark(end_mark)
        
        return True

    undo_list.append(undo)
    
    return True

  