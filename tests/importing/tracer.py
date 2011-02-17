#!/usr/bin/env python



import sys
import types
import builtins
import os.path
sys.path.append('/home/patrick/myprogs/epdb/importing/dbgmods')
import __dbg as dbg

__pythonimport__ = builtins.__import__

def randint(a,b):
    print('Generate number for ', a, ',', b)

def myprint(*args, **kargs):
    print('Hallo Welt')

def __import__(*args):
    print('My import', args[0], args[3], args[4])
    mod = __pythonimport__(*args)
    try:
        getattr(mod, 'print')
        print('Found')
    except:
        pass

    if args[0] == 'random':
        #print(mod.__dict__)
        #print(getattr(mod, 'randint'))
        randmod = __pythonimport__('__random', globals(), locals(), [])
        print(randmod.__dict__.keys())
        for key in randmod.__dict__.keys():
            if key == 'random':
                continue
            if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', '__dbg']:
                continue
            setattr(mod, '__orig__'+key, getattr(mod,key))
            setattr(mod, key, getattr(randmod, key))
        #setattr(mod, 'randint', randint)
    elif args[0] == 'builtins':
        print('Print found')
        #setattr(mod, 'print', myprint)
    return mod

i = 0

def tracefunc(frame, event, arg):
    global i
    if event == 'call':
        return tracefunc
    elif event == 'line':
        if frame.f_code.co_filename == '/home/patrick/myprogs/epdb/importing/tracer.py':
            return tracefunc
        if os.path.basename(frame.f_code.co_filename).startswith('__'):
            return tracefunc

        # i += 1
        dbg.ic += 1
        #print('{filename}:{lineno} {event} {i}'.format(
        #    lineno=frame.f_lineno,
        #    filename=frame.f_code.co_filename,
        #    i=i, event=event))
        #print(frame.f_code.co_filename)
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
        builtins.__import__ = __import__
        sys.path.append('/home/patrick/myprogs/epdb/importing/dbgmods')
        if not isinstance(cmd, types.CodeType):
            cmd = cmd+'\n'
        try:
            exec(cmd, globals, locals)
            print('Number of instructions executed: {0}'.format(dbg.ic))
        #except BdbQuit:
        #    pass
        finally:
            sys.settrace(None)
