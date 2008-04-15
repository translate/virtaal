

def make_undo_buffer():
    buffer = gtk.TextBuffer()
    undo_list = []
    
    #self.connect("begin-user-action", on_begin_user_action, undo_list)
    self.connect("insert-text",       on_insert_text,       undo_list)
    self.connect("delete-range",      on_delete_range,      undo_list)
    #self.connect("end-user-action",   on_end_user_action,   undo_list)
    
    return buffer, undo_list
    

#def on_begin_user_action(textbuffer, undo_list):
#    return True


def undo(undo_list):
    action = undo_list.pop()
    return action()
    
       
def on_delete_range(textbuffer, start, end, undo_list):
    text = self.buffer.get_text(start_iter, end_iter)
    start_mark = buffer.create_mark("start-mark", start_iter, True)        

    def undo():
        buffer.insert(buffer.get_iter_at_mark(start_mark), text)
        buffer.delete_mark(start_mark)
        
        return True
    
    undo_list.append(undo)    
    
    return True
    
    
#def on_end_user_action(textbuffer, undo_list):
#    return True

  
def on_insert_text(textbuffer, iter, text, length, undo_list):
    start_mark = buffer.create_mark("start-mark", iter)
    end_iter   = iter.copy()
    end_iter.forward(length)
    end_mark   = buffer.create_mark("end-mark", end_iter)
    
    def undo():
        buffer.delete(buffer.get_iter_at_mark(start_mark), buffer.get_iter_at_mark(end_mark))
        buffer.delete_mark(start_mark)
        buffer.delete_mark(end_mark)
        
        return True

    undo_list.append(undo)
    
    return True

  