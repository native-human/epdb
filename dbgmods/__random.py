#!/usr/bin/env python

from epdblib import dbg
from epdblib import debug as log

__orig__seed = seed
def seed(a=None):
    if dbg.mode == 'normal':
        __orig__seed(a)
        dbg.snapshottingcontrol.set_make_snapshot()
        return
