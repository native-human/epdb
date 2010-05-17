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
import builtins
import types
import _thread
from debug import debug

sys.path.append('/home/patrick/myprogs/epdb/importing/dbgmods')
import __dbg as dbg

__pythonimport__ = builtins.__import__

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

mode = 'normal'

def __import__(*args):
    
    #debug('My import', args[0], args[3], args[4], sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename)
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'snaphotting.py', '__dbg.py', 'shareddict.py']:
        return __pythonimport__(*args)
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
        if args[0] == 'random':
            debug('Importing random')
            #debug(mod.__dict__)
            #debug(getattr(mod, 'randint'))
            randmod = __pythonimport__('__random', globals(), locals(), [])
            for key in randmod.__dict__.keys():
                if key == 'random':
                    continue
                if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
                    continue
                setattr(mod, '__orig__'+key, getattr(mod,key))
                setattr(mod, key, getattr(randmod, key))
                debug('Patched: ', key)
            #print(mod.__dict__.keys())
            #setattr(mod, 'randint', randint)
        elif args[0][:2] != '__':
            try:
                module = __pythonimport__('__'+args[0], globals(), locals(), [])
            except ImportError:
                pass
            else:
                debug('Importing a module with patching', args[0])
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

class Epdb(pdb.Pdb):
    def __init__(self):
        pdb.Pdb.__init__(self)
        self.init_reversible()
    
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
        locals = globals
        sys.path.append('/home/patrick/myprogs/epdb/importing/dbgmods')

        with open(filename, "rb") as fp:
            debug(fp.read)
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)
        #debug('Test')
        #debug(statement)
        #debug(self.mainpyfile)
        
        #self.reset()
        self.quitting = 0
        self.botframe = None
        self.stopframe = None
        self.returnframe = None
        
        sys.settrace(self.trace_dispatch)
        builtins.__import__ = __import__
        if not isinstance(cmd, types.CodeType):
            statement = statement + '\n'
        try:
            exec(statement, globals, locals)
        except bdb.BdbQuit:
            pass
        finally:
            self.quitting = 1
            sys.settrace(None)
        
        #self.run(statement)
        
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
        
        self.prompt = '(Edpb) '
        self.stopafter = -1
    
    def user_line(self, frame):
        #debug('user_line')
        if self.stopafter > 0:
            #debug('return')
            return
        pdb.Pdb.user_line(self, frame)
        
    #def _runscript(self, filename):
    #    #debug('_runscript', self.stopafter)
    #    self.ic = 0
    #    pdb.Pdb._runscript(self, filename)
    #    #if self.stopafter > 0:
    #    #    debug('continue set')
    #    #    self.set_continue()
    
    def trace_dispatch(self, frame, event, arg):
        # debug("trace_dispatch")
        return pdb.Pdb.trace_dispatch(self, frame, event, arg)
    
    def dispatch_line(self, frame):
        #global mode
        #debug('Line is going to be dispatched: ', frame.f_code.co_filename, frame.f_lineno, self.ic)
        
        #self.ic += 1
        dbg.ic += 1
        
        if self.starting_ic is None:
            if frame.f_code.co_filename == self.mainpyfile:
                #self.starting_ic = self.ic
                self.starting_ic = dbg.ic
            #debug(frame.f_code.co_filename, self.mainpyfile)
        # debug('Line is going to be dispatched: ', self.ic)
        
        if self.stopafter > 0:
            self.stopafter -= 1
        
        if self.stopafter == 0:
            self.stopafter = -1
            debug(dbg.mode)
            dbg.mode = 'normal'
            # debug('stopafter triggered')
            self.set_trace()
            
        return pdb.Pdb.dispatch_line(self, frame)
    
    def dispatch_call(self, frame, arg):
        # debug('dispatch a call: ', frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno)
        
        #if frame.f_code.co_name == 'blah':
        #    debug("inject code: ", self.curframe.f_lineno)

        if self.botframe is None:
            #debug('self.botframe == None')
            # First call of dispatch since reset()
            self.botframe = frame.f_back # (CT) Note that this may also be None!
            return self.trace_dispatch
        # if not (self.stop_here(frame) or self.break_anywhere(frame)) :
        #    # No need to trace this function
        #    return # None
        if os.path.basename(frame.f_code.co_filename).startswith('__'):
            return
        if os.path.basename(frame.f_code.co_filename) in ['random.py', 'builtins.py', 'locale.py', 'codecs.py', 'sys.py', 'encodings.py', 'functools.py', 're.py', 'sre_compile.py', 'sre_parse.py', 'epdb.py', 'posixpath.py', 'hmac.py', 'connection.py', 'managers.py', 'pickle.py', 'threading.py', 'util.py', 'process.py', 'socket.py', 'idna.py', 'os.py', 'shareddict.py']:
            return
        else:
            debug('I am in file: ', frame.f_code.co_filename)
        #debug(frame.f_code.co_filename)
        
        funcname = frame.f_code.co_name
        #debug('Funcname', funcname)
        try:
            #isdebug = getattr(funcname, '__debug__')
            namespace = {}
            namespace.update(frame.f_globals)
            namespace.update(frame.f_locals)
            namespace.update(frame.f_builtins)
            funcobj = namespace[funcname]
        except AttributeError:
            pass
            #debug('AttrError', str(sorted(namespace.keys())))
        except KeyError:
            pass
            #debug('KeyError', str(sorted(namespace.keys())))
        self.user_call(frame, arg)
        if self.quitting: raise BdbQuit
        return self.trace_dispatch

        # return pdb.Pdb.dispatch_call(self, frame, arg)
    
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
        self._set_stopinfo(self.botframe, None)

    def do_snapshot(self, arg, temporary=0):
        #global mode
        #snapshot = snapshotting.Snapshot(self.ic, self.snapshot_id)
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
            self.stopafter = snapshot.step_forward
            self.set_continue()
            return 1
        else:
            return
    
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
        self.set_quit()
        return 1
    
    def do_stepback(self, arg):
        # TODO make a snapshot at the beginning of the program. This is necessary
        # for not doubeling up a filedescriptor, if the program replays after opening
        # a file. The open file descriptor would be closed.
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
            
        
        if snapshot == None:
            if actual_ic == self.starting_ic:
                debug("Can't step back. At the beginning of the program")
            dbg.mode = 'replay'
            self.stopafter = steps
            pdb.Pdb.do_run(self, None) # do_run raises a restart exception
            #return
        
        self.mp.activatesp(snapshot.id, steps)
        raise EpdbExit()
        
        
    def set_quit(self):
        # debug('quit set')
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
            #epdb.ic = 0
            dbg.ic = 0
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
            #print('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            #print('SnapshotExit caught')
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
    #print('Loop finished')
