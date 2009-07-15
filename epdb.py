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
    def __init__(self):
        pdb.Pdb.__init__(self)
        self.prompt = '(Edpb)'
    def do_savepoint(self, arg, temporary=0):
        # savepoint [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            print('Show savepoints')
            for sp in Savepoint.spbynumber:
                if sp:
                    sp.spprint()
            return
        elif len(arg) == 1:
            lineno = 0            
            #try:
            #    lineno = int(arg)
            #except ValueError as msg:
            #    print('*** Bad lineno:', arg, file=self.stdout)
            #    return
            sp = Savepoint(lineno)
        
        filename = None
        lineno = None
        cond = None
        
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()

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

    p = Epdb()
    p.reset()
    p.interaction(None, t)

def pm():
    post_mortem(sys.last_traceback)
    
    # Main program for testing

TESTCMD = 'import x; x.main()'

def test():
    run(TESTCMD)

# print help
def help():
    for dirname in sys.path:
        fullname = os.path.join(dirname, 'pdb.doc')
        if os.path.exists(fullname):
            sts = os.system('${PAGER-more} '+fullname)
            if sts: print('*** Pager exit status:', sts)
            break
    else:
        print('Sorry, can\'t find the help file "pdb.doc"', end=' ')
        print('along the Python search path')

def main():
    if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
        print("usage: pdb.py scriptfile [arg] ...")
        sys.exit(2)

    mainpyfile =  sys.argv[1]     # Get script filename
    if not os.path.exists(mainpyfile):
        print('Error:', mainpyfile, 'does not exist')
        sys.exit(1)

    del sys.argv[0]         # Hide "pdb.py" from argument list

    # Replace pdb's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(mainpyfile)

    # Note on saving/restoring sys.argv: it's a good idea when sys.argv was
    # modified by the script being debugged. It's a bad idea when it was
    # changed by the user from the command line. There is a "restart" command
    # which allows explicit specification of command line arguments.
    epdb = Epdb()
    while 1:
        try:
            epdb._runscript(mainpyfile)
            if epdb._user_requested_quit:
                break
            print("The program finished and will be restarted")
        except Restart:
            print("Restarting", mainpyfile, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
        except SystemExit:
            # In most cases SystemExit does not warrant a post-mortem session.
            print("The program exited via sys.exit(). Exit status: ", end=' ')
            print(sys.exc_info()[1])
        except:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            epdb.interaction(None, t)
            print("Post mortem debugger finished. The " + mainpyfile +
                  " will be restarted")


# When invoked as main program, invoke the debugger on a script
if __name__ == '__main__':
    import epdb
    epdb.main()
