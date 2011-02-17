
import sys
import linecache
import types

class PyDb:
    def tracefunc(self, frame, event, arg):
        import linecache
        import sys
        if event == 'line':
            print('Line: ' + str(frame.f_code.co_filename) + ':' + str(frame.f_lineno) + ':' + linecache.getline(frame.f_code.co_filename, frame.f_lineno))
            print('pydb>>> ')
            input = sys.stdin.readline()
            return self.tracefunc
        return self.tracefunc

    def run(self, cmd, globals=None, locals=None):
        import linecache
        import sys
        import types
        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals

        #self.reset()
        linecache.checkcache()

        sys.settrace(self.tracefunc)
        if not isinstance(cmd, types.CodeType):
            cmd = cmd+'\n'
        try:
            exec(cmd, globals, locals)
        finally:
            sys.settrace(None)

    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        my__builtins__ = __builtins__
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                    "__file__"    : filename,
                                    "__builtins__": my__builtins__,
                                    })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).

        with open(filename) as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                    (fp.read(), filename)
        self.run(statement)

    def start_tracing(self):
        frame = sys._getframe().f_back
        while frame:
            frame.f_trace = self.tracefunc
            frame = frame.f_back
        sys.settrace(self.tracefunc)

if __name__ == '__main__':

    filename = sys.argv[1]
    pydb = PyDb()
    pydb._runscript(filename)
