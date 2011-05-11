import sys
import unittest
import epdblib.basedebugger
import os.path
import time
import operator
import fnmatch

class MyTracer(epdblib.basedebugger.Tracer):
    def __init__(self, skip=[]):
        super().__init__(skip=skip)
        self.lineno_stack = []
        self.modules = {}
        self.dispatched_lines = 0
        self.dispatched_calls = 0
        self.call_mod = []

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
        self.dispatched_lines += 1
        super().dispatch_line(frame)


    def dispatch_call(self, frame):
        #print("dispatch:", frame.f_globals.get('__name__'))
        self.dispatched_calls += 1
        self.call_mod.append(frame.f_globals.get('__name__'))
        super().dispatch_call(frame)

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
        couchdb_modules = ['sre_compile', 'sre_parse', 'pkg_resources',
                                'collections', 'abc', 'decimal', 'threading',
                                'couchdb.client', '_abcoll', '_weakrefset',
                                'calendar', 'codecs', 'copy', 'couchdb',
                                'couchdb.design', 'couchdb.http', 'couchdb.json',
                                'couchdb.mapping', 'datetime', 'dis', 'distutils',
                                'distutils.dep_util', 'distutils.errors',
                                'distutils.log', 'distutils.spawn',
                                'distutils.util', 'email', "email._parseaddr",
                                "email.base64mime", "email.charset", 'posixpath',
                                "email.encoder", "email.errors",
                                "email.feedparser", "email.header",
                                "email.iterators", "email.message",
                                "email.parsers", "email.encoders",
                                "email.parser", "email.quoprimime", "email.utils",
                                "functools", "genericpath", "http",
                                "http.client", 'inspect', 'locale', 'mimetypes',
                                'namedtuple_ArgInfo', 'namedtuple_ArgSpec',
                                'namedtuple_Arguments', 'namedtuple_Attribute',
                                'namedtuple_DecimalTuple',
                                'namedtuple_DefragResult',
                                'namedtuple_FullArgSpec', 'namedtuple_ModuleInfo',
                                'namedtuple_ParseResult', 'namedtuple_SplitResult',
                                'namedtuple_Traceback', 'numbers', 'opcode',
                                'os', 'pkgutil', 'quopri', 're', 'ssl', 'stat',
                                'string', 'textwrap', 'urllib', 'urllib.error',
                                'urllib.parse', 'urllib.request',
                                'urllib.response', 'uu'
                                ]
        tracer = MyTracer(skip=couchdb_modules)
        tracer.run("from couchdb.mapping import Document")
        #print(time.time()-start)
        #print("dispatches: ", len(tracer.lineno_stack))
        #
        #print("dispatched_lines: ", tracer.dispatched_lines)
        #print("dispatched_calls: ", tracer.dispatched_calls)
        #sortedmodules = sorted(tracer.modules.items(), key=operator.itemgetter(0))
        #print(sortedmodules)
        #
        #start = time.time()
        #for m in tracer.call_mod:
        #    for e in couchdb_modules:
        #        if fnmatch.fnmatch(e, m):
        #            break
        #print("Manual time with fnmatch: ", time.time()-start)
        #
        #start = time.time()
        #for m in tracer.call_mod:
        #    for e in couchdb_modules:
        #        if e == m:
        #            break
        #print("Manual time with equals ", time.time()-start)

    def test_skipped_module(self):
        tracer = MyTracer(skip=["skipped_mod"])
        tracer.runscript('call_skipped.py')
        #print(tracer.modules)

if __name__ == '__main__':
    unittest.main()
