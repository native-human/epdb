#!/usr/bin/env python

import random
import __dbg

def randint(a, b):
    def replay(a, b):
        print('replaying randint')
        return __dbg.sde['0']()
    def undo(a, b):
        print('undoing randint')
    def debug(a, b):
        value = random.__orig__randint(a, b)
        #value = 3
        def redo():
            return value
        __dbg.sde['0'] = redo
        print('debugging randint')
        return value
    if __dbg.mode == 'replay':
        return replay(a, b)
    elif __dbg.mode == 'normal':
        return debug(a, b)
    elif __dbg.mode == 'undo':
        return undo(a, b)
    print('This is the modified randint', a, b)
    
    