import sys
import unittest
import epdblib.basedebugger
import os.path
import time
import operator

class MyTracer(epdblib.basedebugger.Tracer):
    def __init__(self, skip=[]):
        super().__init__(skip=skip)
        self.lineno_stack = []
        self.modules = {}

    def user_first(self, frame):
        pass

    def user_line(self, frame):
        modname = frame.f_globals.get('__name__')
        m = self.modules.get(modname)
        if not m:
            self.modules[modname] = 1
        else:
            self.modules[modname] = m+1
        self.lineno_stack.append(frame.f_lineno)

    def dispatch_line(self, frame):
        #print("dispatch:", frame.f_globals.get('__name__'))
        super().dispatch_line(frame)

    def user_call(self, frame):
        pass

    def user_return(self, frame, arg):
        pass

    def user_exception(self, frame, arg):
        pass

    def runscript(self, filename):
        self.mainpyfile = os.path.abspath(filename)
        import builtins
        bltins = builtins
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": bltins,
                                })

        self._wait_for_mainpyfile = 1
        self._user_requested_quit = 0
        with open(filename, "rb") as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)

        self.run(statement, __main__.__dict__)

class TracerTestCase(unittest.TestCase):
    def runTest(self):
        tracer = MyTracer()
        tracer.runscript('tracefile.py')
        self.assertEqual(tracer.lineno_stack, [2,4,6,9, 7])

    def test_importcouchdb(self):
        start = time.time()
        tracer = MyTracer(skip=['sre_compile', 'sre_parse', 'pkg_resources',
                                'collections', 'abc', 'decimal', 'threading'])
        tracer.run("from couchdb.mapping import Document")
        #print(time.time()-start)
        #print(len(tracer.lineno_stack))
        sortedmodules = sorted(tracer.modules.items(), key=operator.itemgetter(1))
        #print(sortedmodules)

    def test_skipped_module(self):
        tracer = MyTracer(skip=["skipped_mod"])
        tracer.runscript('call_skipped.py')
        #print(tracer.modules)

if __name__ == '__main__':
    unittest.main()
