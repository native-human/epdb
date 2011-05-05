
import fnmatch
import sys
import os
import types
from epdblib import breakpoint

class BaseDebuggerQuit(Exception):
    """Exception to quit the debugger"""

class Tracer:
    def __init__(self, skip=None):
        if skip:
            self.skip = set(skip)
        else:
            self.skip = None
        self.quitting = 0

    def set_trace(self, frame=None):
        """Start debugging from `frame`.

        If frame is not specified, debugging starts from caller's frame.
        """
        if frame is None:
            frame = sys._getframe().f_back
        self.reset()
        # Set the tracing function for all previous frames
        # and make self.botframe the first frame
        while frame:
            frame.f_trace = self.trace_dispatch
            self.botframe = frame
            frame = frame.f_back
        self.set_step()
        sys.settrace(self.trace_dispatch)

    def trace_dispatch(self, frame, event, arg):
        if self.quitting:
            return # None
        if event == 'line':
            return self.dispatch_line(frame)
        if event == 'call':
            return self.dispatch_call(frame)
        if event == 'return':
            return self.dispatch_return(frame, arg)
        if event == 'exception':
            return self.dispatch_exception(frame, arg)
        if event == 'c_call':
            return self.trace_dispatch
        if event == 'c_exception':
            return self.trace_dispatch
        if event == 'c_return':
            return self.trace_dispatch
        print('epdblib.basedebugger.dispatch: unknown debugging event:', repr(event))
        return self.trace_dispatch

    def is_skipped_module(self, module_name):
        for pattern in self.skip:
            if fnmatch.fnmatch(module_name, pattern):
                return True
        return False

    def dispatch_line(self, frame):
        if not self._wait_for_mainpyfile:
            self.user_line(frame)
        if self.quitting:
            raise BaseDebuggerQuit
        return self.trace_dispatch

    def dispatch_call(self, frame):
        if self.botframe is None:
            # First call of dispatch since reset()
            self.botframe = frame.f_back # (CT) Note that this may also be None!
            return self.trace_dispatch
        # Don't trace this function, if it should not be traced
        if not self.trace_here(frame):
            return

        if self._wait_for_mainpyfile:
            self._wait_for_mainpyfile = 0
            self.user_first(frame)
        else:
            self.user_call(frame)

        if self.quitting:
            raise BaseDebuggerQuit
        return self.trace_dispatch

    def dispatch_return(self, frame, arg):
        #if self.stop_here(frame) or frame == self.returnframe:
        self.user_return(frame, arg)
        if self.quitting:
            raise BaseDebuggerQuit
        return self.trace_dispatch

    def dispatch_exception(self, frame, arg):
        #if self.stop_here(frame):
        self.user_exception(frame, arg)
        if self.quitting:
            raise BaseDebuggerQuit
        return self.trace_dispatch

    def runeval(self, expr, globals=None, locals=None):
        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals
        self.reset()
        sys.settrace(self.trace_dispatch)
        if not isinstance(expr, types.CodeType):
            expr = expr+'\n'
        try:
            return eval(expr, globals, locals)
        except BaseDebuggerQuit:
            pass
        finally:
            self.quitting = 1
            sys.settrace(None)

    # This method is more useful to debug a single function call.
    def runcall(self, func, *args, **kwds):
        self.reset()
        sys.settrace(self.trace_dispatch)
        res = None
        try:
            res = func(*args, **kwds)
        except BaseDebuggerQuit:
            pass
        finally:
            self.quitting = 1
            sys.settrace(None)
        return res

    def set_quit(self):
        self.stopframe = self.botframe
        self.returnframe = None
        self.quitting = 1
        sys.settrace(None)

    def trace_here(self, frame):
        """Trace here returns true if the frame should be trace. It should be
        traced if it is not in a module, which is listed in the skip list."""
        if self.skip and self.is_skipped_module(frame.f_globals.get('__name__')):
            return False
        return True

    def stop_here(self, frame):
        # (CT) stopframe may now also be None, see dispatch_call.
        # (CT) the former test for None is therefore removed from here.
        if self.skip and self.is_skipped_module(frame.f_globals.get('__name__')):
            return False
        if frame is self.stopframe:
            return frame.f_lineno >= self.stoplineno
        while frame is not None and frame is not self.stopframe:
            if frame is self.botframe:
                return True
            frame = frame.f_back
        return False

    def reset(self):
        import linecache
        linecache.checkcache()
        self.botframe = None
        #self._set_stopinfo(None, None)

    def run(self, cmd, globals=None, locals=None):
        self._wait_for_mainpyfile = 1
        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals
        self.reset()
        sys.settrace(self.trace_dispatch)
        if not isinstance(cmd, types.CodeType):
            cmd = cmd+'\n'
        try:
            exec(cmd, globals, locals)
        except BaseDebuggerQuit:
            pass
        finally:
            self.quitting = 1
            sys.settrace(None)

class BaseDebugger(Tracer):
    def __init__(self, skip=None):
        super().__init__(skip) # TODO delegetion is probably better than template
                               # method here
        self.bpmanager = breakpoint.LocalBreakpointManager()
        #self.breaks = {}
        self.fncache = {}

    def canonic(self, filename):
        if filename == "<" + filename[1:-1] + ">":
            return filename
        canonic = self.fncache.get(filename)
        if not canonic:
            canonic = os.path.abspath(filename)
            canonic = os.path.normcase(canonic)
            self.fncache[filename] = canonic
        return canonic

    def break_here(self, frame):
        filename = self.canonic(frame.f_code.co_filename)
        if not self.bpmanager.file_has_breaks(filename):
            return False
        lineno = frame.f_lineno
        if not self.bpmanager.bp_exists(filename, lineno):
            # The line itself has no breakpoint, but maybe the line is the
            # first line of a function with breakpoint set by function name.
            lineno = frame.f_code.co_firstlineno
            if not self.bpmanager.bp_exists(filename, lineno):
                return False
    
        # flag says ok to delete temp. bp
        (bp, flag) = self.bpmanager.effective(filename, lineno, frame)
        if bp:
            self.currentbp = bp.number
            if (flag and bp.temporary):
                self.do_clear(str(bp.number)) # TODO this looks suspicous, does do_clear exist?
            return True
        else:
            return False

    def _set_stopinfo(self, stopframe, returnframe, stoplineno=-1):
        self.stopframe = stopframe
        self.returnframe = returnframe
        self.quitting = 0
        self.stoplineno = stoplineno

    # Derived classes and clients can call the following methods
    # to affect the stepping state.

    def set_until(self, frame): #the name "until" is borrowed from gdb
        """Stop when the line with the line no greater than the current one is
        reached or when returning from current frame"""
        self._set_stopinfo(frame, frame, frame.f_lineno+1)

    def set_step(self):
        """Stop after one line of code."""
        self._set_stopinfo(None,None)

    def set_next(self, frame):
        """Stop on the next line in or below the given frame."""
        self._set_stopinfo(frame, None)

    def set_return(self, frame):
        """Stop when returning from the given frame."""
        self._set_stopinfo(frame.f_back, frame)

    def set_continue(self):
        # Don't stop except at breakpoints or when finished
        self._set_stopinfo(self.botframe, None)
        if not self.bpmanager.any_break_exists():
            # no breakpoints; run without debugger overhead
            sys.settrace(None)
            frame = sys._getframe().f_back
            while frame and frame is not self.botframe:
                del frame.f_trace
                frame = frame.f_back


    # Derived classes and clients can call the following methods
    # to manipulate breakpoints.  These methods return an
    # error message is something went wrong, None if all is well.
    # Set_break prints out the breakpoint line and file:lineno.
    # Call self.get_*break*() to see the breakpoints or better
    # for bp in Breakpoint.bpbynumber: if bp: bp.bpprint().

    def set_break(self, filename, lineno, temporary=0, cond = None,
                  funcname=None):
        filename = self.canonic(filename)
        import linecache # Import as late as possible
        line = linecache.getline(filename, lineno)
        if not line:
            return 'Line %s:%d does not exist' % (filename,
                                   lineno)
        self.bpmanager.new_breakpoint(filename, lineno, temporary, cond, funcname)

    def clear_break(self, filename, lineno):
        filename = self.canonic(filename)
        self.bpmanager.clear_break(filename, lineno)

    def clear_bpbynumber(self, arg):
        try:
            number = int(arg)
        except:
            return 'Non-numeric breakpoint number (%s)' % arg
        try:
            bp = self.bpmanager.breakpoint_by_number(number)
        except IndexError:
            return 'Breakpoint number (%d) out of range' % number
        if not bp:
            return 'Breakpoint (%d) already deleted' % number
        self.bpmanager.clear_break(bp.file, bp.line)

    def clear_all_file_breaks(self, filename):
        filename = self.canonic(filename)
        if not self.bpmanager.file_has_breaks():
            return 'There are no breakpoints in %s' % filename
        self.bpmanager.clear_all_file_breaks(filename)
        #for line in self.breaks[filename]:
        #    blist = Breakpoint.bplist[filename, line]
        #    for bp in blist:
        #        bp.deleteMe()
        #del self.breaks[filename]

    def clear_all_breaks(self):
        if not self.bpmanager.any_break_exists():
            return 'There are no breakpoints'
        self.bpmanager.clear_all_breaks()

    # I believe I don't need this
    #def get_break(self, filename, lineno):
    #    filename = self.canonic(filename)
    #    
    #    return self.bpmanager.get_break(filename, lineno)

    def get_breaks(self, filename, lineno):
        filename = self.canonic(filename)
        return self.bpmanager.get_breaks(filename, lineno)
        
    def get_file_breaks(self, filename):
        filename = self.canonic(filename)
        self.bpmanager.get_file_breaks()

    def get_all_breaks(self):
        return self.bpmanager.get_all_breaks()

    # Derived classes and clients can call the following method
    # to get a data structure representing a stack trace.

    def get_stack(self, f, t):
        stack = []
        if t and t.tb_frame is f:
            t = t.tb_next
        while f is not None:
            stack.append((f, f.f_lineno))
            if f is self.botframe:
                break
            f = f.f_back
        stack.reverse()
        i = max(0, len(stack) - 1)
        while t is not None:
            stack.append((t.tb_frame, t.tb_lineno))
            t = t.tb_next
        if f is None:
            i = max(0, len(stack) - 1)
        return stack, i

    #
    def format_stack_entry(self, frame_lineno, lprefix=': '):
        import linecache, reprlib
        frame, lineno = frame_lineno
        filename = self.canonic(frame.f_code.co_filename)
        s = '%s(%r)' % (filename, lineno)
        if frame.f_code.co_name:
            s = s + frame.f_code.co_name
        else:
            s = s + "<lambda>"
        if '__args__' in frame.f_locals:
            args = frame.f_locals['__args__']
        else:
            args = None
        if args:
            s = s + reprlib.repr(args)
        else:
            s = s + '()'
        if '__return__' in frame.f_locals:
            rv = frame.f_locals['__return__']
            s = s + '->'
            s = s + reprlib.repr(rv)
        line = linecache.getline(filename, lineno, frame.f_globals)
        if line: s = s + lprefix + line.strip()
        return s