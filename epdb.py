import pdb
import sys
import linecache
import cmd
import bdb
from reprlib import Repr
import os
import os.path
import re
import pprint
import traceback
import snapshotting
import builtins
import types
import _thread
import configparser
from debug import debug

#dbgpath = '/home/patrick/myprogs/epdb/dbgmods'
#sys.path.append(dbgpath)
#sys.path.append('/home/patrick/myprogs/epdb/dbgmods')

dbgpath = None

def readconfig():
    global dbgpath
    sys.path = origpath
    try:
        config = configparser.ConfigParser()
        config.read(os.path.expanduser("~/.config/epdb.conf"))
        dbgmods = config.get('Main', 'dbgmods')
    except:
        dbgmods = '/home/patrick/myprogs/epdb/dbgmods'
    dbgpath = dbgmods
    sys.path.append(dbgmods)

origpath = sys.path[:]
readconfig()

#debug("PATH: ", sys.path)

import dbg

__pythonimport__ = builtins.__import__

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

mode = 'normal'

def __import__(*args):
    #debug("myimport", args[0], sys.path)
    #debug('My import', args[0], args[3], args[4], sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename)
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'snaphotting.py', 'dbg.py', 'shareddict.py', 'debug.py', 'bdb.py', "cmd.py", "fnmatch.py"]:
        return __pythonimport__(*args)
    else:
        #debug("Importing", os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename))
        #debug("ic: ", dbg.ic)
        pass
    new = True
    if args[0] in dbg.modules:
        new = False
    mod = __pythonimport__(*args)
    #try:
    #    getattr(mod, 'print')
    #    debug('Found')
    #except:
    #    pass
    
    if new:
        dbg.modules.append(args[0])
        #debug('new found', args[0], dbg.modules)
        #if args[0] == 'random':
        #    debug('Importing random')
        #    #debug(mod.__dict__)
        #    #debug(getattr(mod, 'randint'))
        #    randmod = __pythonimport__('__random', globals(), locals(), [])
        #    for key in randmod.__dict__.keys():
        #        if key == 'random':
        #            continue
        #        if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
        #            continue
        #        setattr(mod, '__orig__'+key, getattr(mod,key))
        #        setattr(mod, key, getattr(randmod, key))
        #        debug('Patched: ', key)
        #    #print(mod.__dict__.keys())
        #    #setattr(mod, 'randint', randint)
        if args[0][:2] != '__':
            try:
                module = __pythonimport__('__'+args[0], globals(), locals(), [])
                #debug("success")
            except ImportError:
                pass
                #debug("nosuccess", sys.path)
            else:
                #debug('Importing a module with patching', args[0])
                for key in module.__dict__.keys():
                    if key == args[0]:
                        continue
                    if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
                        continue
                    
                    # if the name doesn't exist in the original file -> ignore it
                    try:
                        setattr(mod, '__orig__'+key, getattr(mod,key))
                        setattr(mod, key, getattr(module, key))
                    except AttributeError:
                        pass
                
        #elif args[0] == 'builtins':
        #    debug('Print found')
            #setattr(mod, 'print', myprint)
    return mod

class side_effects:
    def __init__(self, replay, undo):
        self.replay = replay
        self.undo = undo
    def __call__(self, func):
        def newfunc(*args, **kargs):
            f = {'replay':self.replay, 'undo':self.undo, 'normal':func}[mode]
            return f(*args, **kargs)
        newfunc.__debug__ = True
        return newfunc
    __call__.__debug__ = True


def nothing(*args, **kargs):
    return

#@side_effects(undo=nothing, replay=nothing)
#def println(*args, **kargs):
#    debug(*args, **kargs)

class EpdbExit(Exception):
    """Causes a debugger to be exited for the debugged python process."""
    pass

class EpdbPostMortem(Exception):
    """Raised when the program finishes and enters a interactive shell"""
    pass

class Epdb(pdb.Pdb):
    def __init__(self):
        pdb.Pdb.__init__(self, skip=['random', 'debug', 'fnmatch', 'epdb', 'posixpath', 'shareddict', 'pickle'])
        self.init_reversible()
    
    def is_skipped_module(self, module_name):
        """Extend to skip all modules that start with double underscore"""
        #debug('Check ', module_name)
        base = pdb.Pdb.is_skipped_module(self, module_name)
        if base == True:
            #debug("return True")
            return True
        
        if module_name == '__main__':
            #debug("return False")
            return False
        #debug("return", module_name.startswith('__'))
        return module_name.startswith('__')
    
    def make_snapshot(self):
        snapshot = snapshotting.Snapshot(dbg.ic, self.snapshot_id)
        self.psnapshot = self.snapshot
        self.psnapshot_id = self.snapshot_id
        self.pss_ic = self.ss_ic
        self.snapshot = snapshot
        self.snapshot_id = snapshot.id
        # self.ss_ic = self.ic
        self.ss_ic = dbg.ic
        # debug("step_forward: {0}".format(snapshot.step_forward))
        if snapshot.step_forward > 0:
            dbg.mode = 'replay'
            #debug ('mode replay')
            debug('step forward: ', snapshot.step_forward, 'instructions')
            self.stopafter = snapshot.step_forward + 1
            debug('Initial stopafter: ', self.stopafter, 'instructions')
            #self.set_continue()
            return 1
        else:
            return
    
    def precmd(self, line):
        #debug("precommand")
        return line

    def preloop(self):
        #    dbg.ic = 0
        #    self.make_snapshot()
        #    debug('snapshot made')
        debug("ic: ", dbg.ic)
    
    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": __builtins__,
                                })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = 0
        globals = __main__.__dict__
        #locals = globals
        debug("##################",dbgpath)
        sys.path.append('/home/patrick/myprogs/epdb/dbgmods')

        with open(filename, "rb") as fp:
            debug(fp.read)
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)
        self.run(statement)
        
    def init_reversible(self):
        self.mp = snapshotting.MainProcess()
        
        #self.ic = 0             # Instruction Counter
        dbg.ic = 0
        
        self.starting_ic = None
        
        self.ss_ic = 0
        self.snapshot = None
        self.snapshot_id = None
        
        self.pss_ic = 0
        self.psnapshot = None
        self.psnapshot_id = None
        
        self.prompt = '(Epdb) '
        self.running_mode = None
        self.stopafter = -1
        
        # The call_stack contains ic for every call in a previous frame
        # This is used in user_return to find its corresponding call
        self.call_stack = []
        
        # In rnext_ic the position for the rnext command to jump to is saved
        # It is filled in user_return
        self.rnext_ic = {}
        
    
    def trace_dispatch(self, frame, event, arg):
        # debug("trace_dispatch")
        return pdb.Pdb.trace_dispatch(self, frame, event, arg)
    
    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        debug('Line is going to be dispatched: ', frame.f_code.co_filename, frame.f_lineno, dbg.ic)
        #debug("stopafter: ", self.stopafter)
        
        if self.running_mode == 'continue':
            dbg.ic += 1
            if self.break_here(frame):
                self.interaction(frame, None)
        elif self.running_mode == 'next':
            dbg.ic += 1
            if self.nocalls <= 0:
                self.interaction(frame, None)
            if self.break_here(frame):
                self.interaction(frame, None)
        else:
            if self._wait_for_mainpyfile:
                debug('_wait_for_mainpyfile')
                if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno<= 0):
                    debug('Not found')
                    return
                debug('Found', self.stopafter)
                self.make_snapshot()
                self._wait_for_mainpyfile = 0
                #self.skip.add("__main__")
            else:
                dbg.ic += 1
            
            debug("!!!!!!!!!!")
            if self.starting_ic is None:
                if frame.f_code.co_filename == self.mainpyfile:
                    #self.starting_ic = self.ic
                    self.starting_ic = dbg.ic
                    debug("starting ic: ", self.starting_ic)
                #debug(frame.f_code.co_filename, self.mainpyfile)
            # debug('Line is going to be dispatched: ', self.ic)
            
            debug('stopafter: ', self.stopafter)
            if self.stopafter > 0:
                #debug('stopafter > 0')
                self.stopafter -= 1
            
            if self.stopafter == 0:
                #debug('stopafter == 0')
                self.stopafter = -1
                debug(dbg.mode)
                dbg.mode = 'normal'
                self.set_trace()
            
            if self.bp_commands(frame) and self.stopafter == -1:
                debug("Interaction")
                self.interaction(frame, None)
        
    def user_call(self, frame, argument_list):
        debug('User call: ', frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno, dbg.ic)
        
        self.call_stack.append(dbg.ic)
        
        #raise EpdbExit()
        if dbg.mode == 'replay':
            pass
        elif self.running_mode == 'continue':
            pass
        elif self.running_mode == 'next':
            self.nocalls += 1
        else:
            if self._wait_for_mainpyfile:
                debug("User call waiting for mainpyfile")
                return
            #if self.stop_here(frame):
            #    debug('--Call--')
            debug('Calling interaction')
            self.interaction(frame, None)
    
    def stop_here(self, frame):
        #debug('Stop here')
        if pdb.Pdb.stop_here(self, frame):
            #debug('stop found')
            return True
        return False
    
    def break_here(self, frame):
        #debug('Break here')
        if pdb.Pdb.break_here(self, frame):
            #debug('Breakpoint found')
            return True
        return False

    def set_continue(self):
        # Debugger overhead needed to count instructions
        #self._set_stopinfo(None, None)
        self.set_step()
        self.running_mode = 'continue'

    def do_snapshot(self, arg, temporary=0):
        #global mode
        #snapshot = snapshotting.Snapshot(self.ic, self.snapshot_id)
        self.make_snapshot()
    
    def do_restore(self, arg):
        try:
            id = int(arg)
        except:
             debug('You need to supply an index, e.g. restore 0')
             return
        # debug('restore {0}'.format(arg))
        self.mp.activatesp(id)
        # self.set_quit()
        #debug('raise EpdbExit()')
        raise EpdbExit()
    
    def do_ude(self, arg):
        debug('ude:', dbg.ude)
    
    def do_sde(self, arg):
        debug('sde:', dbg.sde)
    
    def do_epdbexit(self, arg):
        raise EpdbExit()
    
    def do_snapshots(self, arg):
        self.mp.list_savepoints()
    
    def do_stopafter(self, arg):
        steps = int(arg)
        self.stopafter = steps
    
    def do_init(self, arg):
        self.init_reversible()
    
    def do_ic(self, arg):
        debug('The instruction count is:', dbg.ic)
        
    def do_quit(self, arg):
        self._user_requested_quit = 1
        self.mp.quit()
        self.set_quit()
        return 1
    
    def do_rstep(self, arg):
        actual_ic = dbg.ic
        snapshot_ic = self.ss_ic
        steps = actual_ic - snapshot_ic - 1
        
        snapshot = self.snapshot
        
        # Undo last step
        try:
            dbg.ude[dbg.ic - 1]()
            del dbg.ude[dbg.ic - 1]
        except KeyError:
            pass
        
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return
        
        if snapshot == None:
            debug("No snapshot made. Can't step back")
            return
        
        if snapshot_ic == actual_ic:
            # Position is at a snapshot. Go to parent snapshot and step forward.
            # TODO
            debug('At a snapshot. Backstepping over a snapshot not implemented yet')
            if self.psnapshot == None:
                #debugging('Backstepping over a snapshot to the beginning of the program not implemented yet.')
                self.snapshot = None
                self.psnapshot = None
                dbg.mode = 'replay'
                self.stopafter = steps
                pdb.Pdb.do_run(self, None) # raises restart exception
                # return
            steps = actual_ic - self.pss_ic - 1
            self.mp.activatesp(self.psnapshot.id, steps)
            raise EpdbExit()
        
        debug('snapshot activation')
        self.mp.activatesp(snapshot.id, steps)
        raise EpdbExit()
        
    def do_rnext(self, arg):
        nextic = self.rnext_ic.get(dbg.ic, dbg.ic-1)
        
        actual_ic = dbg.ic
        snapshot_ic = self.ss_ic
        steps = nextic - snapshot_ic
        
        snapshot = self.snapshot
        
        # Undo last steps
        for i in range(dbg.ic, nextic,-1):
            debug("undo ic: ", i)
            try:
                dbg.ude[dbg.ic - i - 1]()
                del dbg.ude[dbg.ic - i -1]
            except KeyError:
                pass
            
        if snapshot_ic >= nextic:
            # Position is at a snapshot. Go to parent snapshot and step forward.
            # TODO
            debug('At a snapshot. Backstepping over a snapshot not implemented yet')
            debug("snapshotic: ", snapshot_ic)
            debug("nextic: ", nextic)
            return
        
        self.mp.activatesp(snapshot.id, steps)
        raise EpdbExit()
        
    def set_next(self, frame):
        """Stop on the next line in or below the given frame."""
        #self._set_stopinfo(None, None)
        self.set_step()
        self.running_mode = 'next'
        self.nocalls = 0 # Increased on call - decreased on return
        
    def set_quit(self):
        # debug('quit set')
        #self.mp.quit()
        pdb.Pdb.set_quit(self)
    
    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        
        callic = self.call_stack.pop()
        self.rnext_ic[dbg.ic + 1] = callic
        
        if  self.running_mode == 'continue':
            pass
        elif  self.running_mode == 'next':
            self.nocalls -= 1
        else:
            frame.f_locals['__return__'] = return_value
            debug('--Return--')
            self.interaction(frame, None)
    
    def do_rnext_ic(self, arg):
        debug(self.rnext_ic)

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
            #epdb.ic = 0
            dbg.ic = 0
            epdb._runscript(mainpyfile)
            if epdb._user_requested_quit:
                break
            #print("The program finished and will be restarted")
            print("The program has finished", dbg.ic)
            raise EpdbPostMortem()
            #epdb.interaction(None, None)
        except pdb.Restart:
            print("Restarting", mainpyfile, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
            # Deactivating automatic restart temporarily TODO
            break
        except SystemExit:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            epdb.interaction(None, t)
        except EpdbExit:
            debug('EpdbExit caught')
            break
            # sys.exit(0)
        except bdb.BdbQuit:
            debug('BdbQuit caught - Shutting servers down')
            break
        except snapshotting.ControllerExit:
            debug('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            debug('SnapshotExit caught')
            break
        except EpdbPostMortem:
            t = sys.exc_info()[2]
            epdb.mp.quit()
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
else:
    debug("ELSEELSE")
    #print('Loop finished')
#print("Finished")
