#!/usr/bin/env python

import sys
import types
import tracer

if __name__ == '__main__':
    import importing
    mainpyfile =  sys.argv[1]
    tr = tracer.Tracer()
    with open(mainpyfile, "rb") as fp:
        cmd = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), mainpyfile)

    tr.execfilename(cmd, mainpyfile)