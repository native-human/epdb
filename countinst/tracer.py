#!/usr/bin/env python



import sys
import types

i = 0

def tracefunc(frame, event, arg):
    global i
    i += 1
    if event == 'call':
        return tracefunc
    elif event == 'line':
        #print('{filename}:{lineno} {event} {i}'.format(
        #    lineno=frame.f_lineno,
        #    filename=frame.f_code.co_filename,
        #    i=i, event=event))
        return tracefunc
    elif event == 'return':
        return tracefunc
    elif event == 'exception':
        return tracefunc
    else:
        print('unexpected event {0}'.format(event))
        
    return tracefunc

class Tracer:
    def execfilename(self, cmd, filename):
        import __main__
        __main__.__dict__.clear()
        #print("{}".format(__main__))
        __main__.__dict__.update({"__name__"    : "__main__",
                                 "__file__"    : filename,
                                  "__builtins__": __builtins__,
                                 })
        # frm = sys._getframe()
        # while frm != None:
        #    lineno = frm.f_lineno
        #    filename = frm.f_code.co_filename
        #    print('{} {}'.format(filename, lineno))
        #    frm.f_trace = tracefunc
        #    frm = frm.f_back
        globals = __main__.__dict__
        locals = globals
        sys.settrace(tracefunc)
        if not isinstance(cmd, types.CodeType):
            cmd = cmd+'\n'
        try:
            exec(cmd, globals, locals)
            print('Number of instructions executed: {0}'.format(i))
        #except BdbQuit:
        #    pass
        finally:
            sys.settrace(None)