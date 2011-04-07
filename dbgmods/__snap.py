from epdblib import dbg

__orig__foo = foo
def foo():
    dbg.snapshottingcontrol.set_make_snapshot()
    return __orig__foo()
