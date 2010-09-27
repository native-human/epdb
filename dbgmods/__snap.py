
import dbg
import snap

def foo():
    dbg.snapshottingcontrol.set_make_snapshot()
    return snap.__orig__foo()