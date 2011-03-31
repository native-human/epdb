#!/usr/bin/env python

#import time as timemod
#from time import __orig__time
from epdblib import dbg
from epdblib import debug as log

__orig__time = time
def time():
    if dbg.is_dbg_callee():
        return __orig__time()
    if dbg.mode == 'normal':
        r = __orig__time()
        dbg.snapshottingcontrol.set_make_snapshot()
        return r
