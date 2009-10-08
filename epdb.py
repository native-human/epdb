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
        print('Savepoint created: {0}'.format(lineno))
        self.lineno = lineno
        self.spbynumber.append(self)
    def spprint(self, out = None):
        if out == None:
            out = sys.stdout
        print('Savepoint %d' % self.lineno)
    

class Epdb(pdb.Pdb):
    def __init__(self):
        pdb.Pdb.__init__(self)
        self.prompt = '(Edpb) '
        
    def _runscript(self, filename):
        print('_runscript')
        pdb.Pdb._runscript(self, filename)
    
    def dispatch_line(self, frame):
        #print('Line is going to be dispatched: ', frame.f_lineno)
        return pdb.Pdb.dispatch_line(self, frame)    
    
    def set_save(self, filename, lineno, temporary=0, cond = None,
                  funcname=None):
        sp = Savepoint(lineno)
    
    def break_here(self, frame):
        if pdb.Pdb.break_here(self, frame):
            print('Breakpoint found')
            return True
        return False
        
        #filename = self.canonic(frame.f_code.co_filename)
        #if not filename in self.breaks:
        #    return False
        #lineno = frame.f_lineno
        #if not lineno in self.breaks[filename]:
        #    # The line itself has no breakpoint, but maybe the line is the
        #    # first line of a function with breakpoint set by function name.
        #    lineno = frame.f_code.co_firstlineno
        #    if not lineno in self.breaks[filename]:
        #        return False
        #
        ## flag says ok to delete temp. bp
        #(bp, flag) = effective(filename, lineno, frame)
        #if bp:
        #    self.currentbp = bp.number
        #    if (flag and bp.temporary):
        #        self.do_clear(str(bp.number))
        #    return True
        #else:
        #    return False
    
    def do_savepoint(self, arg, temporary=0):
        # savepoint [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            print('Show savepoints')
            for sp in Savepoint.spbynumber:
                if sp:
                    sp.spprint()
            return
        #elif len(arg) == 1:
        #    lineno = 0            
        #    #try:
        #    #    lineno = int(arg)
        #    #except ValueError as msg:
        #    #    print('*** Bad lineno:', arg, file=self.stdout)
        #    #    return
        #    sp = Savepoint(lineno)
        
        filename = None
        lineno = None
        cond = None
        
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()

        colon = arg.rfind(':')
        funcname = None

        if colon >= 0:
            filename = arg[:colon].rstrip()
            f = self.lookupmodule(filename)
            if not f:
                print('*** ', repr(filename))
                print('not found from sys.path')
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError as msg:
                print('*** Bad lineno:', arg)
                return
        else:
            # no colon; can be lineno or function
            try:
                lineno = int(arg)
            except ValueError:
                try:
                    func = eval(arg,
                                self.curframe.f_globals,
                                self.curframe_locals)
                except:
                    func = arg
                try:
                    if hasattr(func, '__func__'):
                        func = func.__func__
                    code = func.__code__
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        print('*** The specified object')
                        print(repr(arg))
                        print('is not a function')
                        print('or was not found along sys.path.')
                        return
                    funcname = ok # ok contains a function name
                    lineno = int(ln)
        if not filename:
            filename = self.defaultFile()
        
        line = self.checkline(filename, lineno)
        if line:
            # now set the save point
            err = self.set_save(filename, line, temporary, cond, funcname)
            if err:
                print('***', err)
            #else:
            #    bp = self.get_breaks(filename, line)[-1]
            #    print("Breakpoint %d at %s:%d" % (bp.number,
            #                                      bp.file,
            #                                      bp.line))

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
            # In most cases SystemExit does not warrant a post-mortem session.
            pass
            #print("The program exited via sys.exit(). Exit status: ", end=' ')
            #print(sys.exc_info()[1])
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
