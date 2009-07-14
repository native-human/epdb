import pdb
import sys
import linecache
import cmd
import bdb
from reprlib import Repr
import os
import re
import pprint
import traceback

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

class Savepoint:
    spbynumber = [None]
    def __init__(self, lineno):
        self.lineno = lineno
        self.spbynumber.append(self)
    def spprint(self, out = None):
        if out == None:
            out = sys.stdout
        print('Savepoint %d' % self.lineno)
    

class Epdb(pdb.Pdb):
    def do_savepoint(self, arg, temporary=0):
        if not arg:
            print('Show savepoints')
            for sp in Savepoint.spbynumber:
                if sp:
                    sp.spprint()
            return
        elif len(arg) == 1:
            lineno = 0            
            try:
                lineno = int(arg)
            except ValueError as msg:
                print('*** Bad lineno:', arg, file=self.stdout)
                return
            sp = Savepoint(lineno)
        
        

def run(statement, globals=None, locals=None):
    Epdb().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Epdb().runeval(expression, globals, locals)

def runctx(statement, globals, locals):
    # B/W compatibility
    run(statement, globals, locals)

def runcall(*args, **kwds):
    return Epdb().runcall(*args, **kwds)

def set_trace():
    Epdb().set_trace(sys._getframe().f_back)

# Post-Mortem interface

def post_mortem(t=None):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
        if t is None:
            raise ValueError("A valid traceback must be passed if no "
                                               "exception is being handled")

    p = Pdb()
    p.reset()
    p.interaction(None, t)

def pm():
    post_mortem(sys.last_traceback)
