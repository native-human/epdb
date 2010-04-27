#!/usr/bin/env python

import random
import __dbg as dbg

def randint(a, b):
    def replay(a, b):
        print('replaying randint', dbg.ic, dbg.sde)
        return dbg.sde[dbg.ic]
    def undo(a, b):
        print('undoing randint')
    def debug(a, b):
        value = random.__orig__randint(a, b)
        #def redo():
        #    return value
        #dbg.sde[dbg.ic] = redo
        dbg.sde[dbg.ic] = value
        print('debugging randint')
        return value
    if dbg.mode == 'replay':
        return replay(a, b)
    elif dbg.mode == 'normal':
        return debug(a, b)
    elif __dbg.mode == 'undo':
        return undo(a, b)
    print('This is the modified randint', a, b)
    
    