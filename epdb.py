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
import snapshotting

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

class EpdbExit(Exception):
    """Causes a debugger to be exited for the debugged python process."""
    pass

class Epdb(pdb.Pdb):
    def __init__(self):
        pdb.Pdb.__init__(self)
        self.ic = 0             # Instruction Counter
        self.init_reversible()
        
    def init_reversible(self):
        self.mp = snapshotting.MainProcess()
        self.psnapshot = None # TODO parent snapshots
        self.prompt = '(Edpb) '
        self.stopafter = -1
        
    def _runscript(self, filename):
        # print('_runscript')
        pdb.Pdb._runscript(self, filename)
    
    def trace_dispatch(self, frame, event, arg):
        print("trace_dispatch")
        return pdb.Pdb.trace_dispatch(self, frame, event, arg)
    
    def dispatch_line(self, frame):
        print('Line is going to be dispatched: ', frame.f_lineno)
        self.ic += 1
        if self.stopafter == 0:
            print('stopafter triggered')
            self.set_trace()
        elif self.stopafter > 0:
            self.stopafter -= 1
        return pdb.Pdb.dispatch_line(self, frame)    
    
    #def set_save(self, filename, lineno, temporary=0, cond = None,
    #              funcname=None):
    #    sp = Savepoint(lineno)
    
    def stop_here(self, frame):
        #print('Stop here')
        if pdb.Pdb.stop_here(self, frame):
            #print('stop found')
            return True
        return False
    
    def break_here(self, frame):
        #print('Break here')
        if pdb.Pdb.break_here(self, frame):
            #print('Breakpoint found')
            return True
        return False

    def do_snapshot(self, arg, temporary=0):
        snapshot = snapshotting.Snapshot(self.ic, self.psnapshot)
        self.psnapshot = snapshot.id
    
    def do_restore(self, arg):
        try:
            id = int(arg)
        except:
             print('You need to supply an index, e.g. restore 0')
             return
        # print('restore {0}'.format(arg))
        self.mp.activatesp(id)
        # self.set_quit()
        print('raise EpdbExit()')
        raise EpdbExit()
    
    def do_epdbexit(self, arg):
        raise EpdbExit()
    
    def do_snapshots(self, arg):
        self.mp.list_savepoints()
    
    def do_stopafter(self, arg):
        steps = int(arg)
        self.stopafter = steps
    
    def do_init(self, arg):
        self.init_reversible()
        
    def do_quit(self, arg):
        self._user_requested_quit = 1
        self.set_quit()
        return 1
        
    def set_quit(self):
        print('quit set')
        self.mp.quit()
        pdb.Pdb.set_quit(self)

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
        fullname = os.path.join(dirname, 'epdb.doc')
        if os.path.exists(fullname):
            sts = os.system('${PAGER-more} '+fullname)
            if sts: print('*** Pager exit status:', sts)
            break
    else:
        pass
        #print('Sorry, can\'t find the help file "epdb.doc"', end=' ')
        #print('along the Python search path')

def main():
    if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
        print("usage: epdb.py scriptfile [arg] ...")
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
        except pdb.Restart:
            print("Restarting", mainpyfile, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
        except SystemExit:
            print('SystemExit caught')
            # In most cases SystemExit does not warrant a post-mortem session.
            pass
            #print("The program exited via sys.exit(). Exit status: ", end=' ')
            #print(sys.exc_info()[1])
        except EpdbExit:
            #print('EpdbExit caught')
            break
            # sys.exit(0)
        except snapshotting.ControllerExit:
            print('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            print('SnapshotExit caught')
            break
        except:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            epdb.interaction(None, t)
            
            #print("Post mortem debugger finished. The " + mainpyfile +
            #      " will be restarted")
            


# When invoked as main program, invoke the debugger on a script
if __name__ == '__main__':
    import epdb
    epdb.main()
    print('Loop finished')
