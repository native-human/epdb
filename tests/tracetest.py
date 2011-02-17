

import sys
import linecache
import os.path

inject = False

class side_effects:
    def __init__(self, replay, undo):
        self.replay = replay
        self.undo = undo
    def __call__(self, func):
        def newfunc(*args, **kargs):
            if mode == 'replay':
                print('replay')
                return self.replay(*args, **kargs)
            elif mode == 'undo':
                return self.undo(*args, **kargs)
            return func(*args, **kargs)
        newfunc.__debug__ = True
        return newfunc

def nothing(*args, **kargs):
    pass

@side_effects(replay=nothing, undo=nothing)
def println(*args, **kargs):
    print(*args, **kargs)

print('blah: ' + str(println.__debug__))

sys.exit(0)

def replay():
    print('replay')

def tracefunc(frame, event, arg):
    global inject
    if event == 'line':
        if inject == True:
            replay()
            inject = False
            #def blah():
            #    pass
            #frame.f_code = blah.__code__
            #frame.f_lineno += 2
            #print('Line(' +  str(frame.f_lasti) + ',' + str(len(frame.f_code.co_code)) + '): '
            #      + str(frame.f_code.co_filename) + ':' + str(frame.f_lineno)
            #      + ':'
            #      + linecache.getline(frame.f_code.co_filename, frame.f_lineno))
            #frame.f_lineno += 1
        return tracefunc
    if event == 'call':
        #print('Call: ' + str(frame.f_code.co_filename))
        #print('Function name: ', str(frame.f_code.co_name))
        #print('Argcount: ', str(frame.f_code.co_argcount))
        #print('Nlocals: ', str(frame.f_code.co_nlocals))
        #print('Varnames: ', str(frame.f_code.co_varnames))
        #print('Varnames: ', str(frame.f_code.co_cellvars))
        #print('Freevars: ', str(frame.f_code.co_freevars))
        #print('Consts: ', str(frame.f_code.co_consts))
        #print('Names: ', str(frame.f_code.co_names))
        #print('Filename: ', str(frame.f_code.co_filename))
        #print('Firstlineneo: ', str(frame.f_code.co_firstlineno))
        #print('lnotab: ', str(frame.f_code.co_lnotab))
        #print('Stacksize: ', str(frame.f_code.co_stacksize))
        #print('Flags: ', str(frame.f_code.co_flags))
        #print('Code: ', str(frame.f_code.co_code))

        if frame.f_code.co_name == 'inp':
            print("inject code")
            print("Lineno: ", str(frame.f_lineno))
            inject = True
            #frame.f_lineno += 1
            def blah():
                pass
            #frame.f_code = blah.__code__
            # frame.f_code.co_code = b'd\x00\x00S'
        #print(', '.join(map(str, [frame.f_code.co_name,
        #                  frame.f_code.co_argcount,
        #                  frame.f_code.co_nlocals,
        #                  frame.f_code.co_varnames,
        #                  frame.f_code.co_cellvars,
        #                  frame.f_code.co_freevars,
        #                  frame.f_code.co_consts,
        #                  frame.f_code.co_names,
        #                  frame.f_code.co_filename,
        #                  frame.f_code.co_firstlineno,
        #                  frame.f_code.co_lnotab,
        #                  frame.f_code.co_stacksize,
        #                  frame.f_code.co_flags])))

        return tracefunc
    if event == 'return':
        inject = False
        print('Return')
        return tracefunc
    if event == 'exception':
        print('Exception')
        return tracefunc
    if event == 'c_call':
        print('c_call')
        return tracefunc
    if event == 'c_exception':
        print('c_exception')
        return tracefunc
    if event == 'c_return':
        print('c_return')
        return tracefunc
    print('Unknown event')
    return tracefunc

def start_logging():
    frame = sys._getframe().f_back
    while frame:
        frame.f_trace = tracefunc
        frame = frame.f_back
    sys.settrace(tracefunc)

#start_logging()
mode = 'normal'

def nondeterministic(func):
    if mode == 'replay':
        return func.replay
    elif mode == 'undo':
        return func.undo
    return func


class nondeterministic:
    def __init__(self, replay, undo):
        self.replay = replay
        self.undo = undo
    def __call__(self, func):
        if mode == 'replay':
            return self.replay
        elif mode == 'undo':
            return self.undo
        return func

def myprint_replay():
    print('replay')

def myprint_undo():
    print('undo')

@nondeterministic(myprint_replay, myprint_undo)
def myprint():
    print('blabla')

myprint()

sys.exit(0)

class X:
    pass

#def blah():
#    return 'blah'

#def yahoo(x):
#    blah()
#    x = 2 + 1
#    return 'x'


def inp():
    print('Input')
    print('Input2')

def empty():
    pass

inp()
empty()

#os.path.join("a","b")

# x = input()

#print('Hello World')

#x = 3 + 4 +34 +54
#print(yahoo(3))
