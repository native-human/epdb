#!/usr/bin/env python

import random
import dbg
import debug as log

#def randint(a, b):
#    def replay(a, b):
#        log.debug('Replaying randint', dbg.ic)
#        return dbg.nde[dbg.ic]
#    def undo(a, b):
#        log.debug('undoing randint')
#    def debug(a, b):
#        value = random.__orig__randint(a, b)
#        dbg.nde[dbg.ic] = value
#        log.debug('debugging randint')
#        return value
#    def redo(a, b):
#        log.debug("redoing randint")
#        return dbg.nde[dbg.ic]
#    log.debug('This is the modified randint', a, b)
#    if dbg.mode == 'replay':
#        return replay(a, b)
#    elif dbg.mode == 'normal':
#        return debug(a, b)
#    elif dbg.mode == 'redo':
#        return redo(a, b)
#    elif dbg.mode == 'undo':
#        return
   
def seed(a=None):
    def replay(a):
        log.debug('Replaying seed', dbg.ic)
    def undo(a):
        log.debug('undoing seed')
    def debug(a):
        log.debug('debugging seed')
        random.__orig__seed(a)
        dbg.snapshottingcontrol.set_make_snapshot()
        return
    def redo(a):
        log.debug("redoing seed")
        return
    if dbg.mode == 'replay':
        return replay(a)
    elif dbg.mode == 'normal':
        return debug(a)
    elif dbg.mode == 'redo':
        return redo(a)
    elif dbg.mode == 'undo':
        return