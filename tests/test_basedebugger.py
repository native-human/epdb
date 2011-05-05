import epdblib.basedebugger
import unittest
from helpers import CoverageTestCase
import sys

def bar(a):
    print('bar(', a, ')')
    return a/2

def foo(n):
    print('foo(', n, ')')
    x = bar(n*10)
    print('bar returned', x)

class Tdb(epdblib.basedebugger.BaseDebugger):
    def __init__(self):
        super().__init__()
        self.calls = 0
    def user_first(self, frame):
        pass
    def user_call(self, frame):
        self.calls += 1
        name = frame.f_code.co_name
        if not name: name = '???'
        print('+++ call', name, self.calls)
    def user_line(self, frame):
        import linecache
        name = frame.f_code.co_name
        if not name: name = '???'
        fn = self.canonic(frame.f_code.co_filename)
        line = linecache.getline(fn, frame.f_lineno, frame.f_globals)
        print('+++', fn, frame.f_lineno, name, ':', line.strip())
    def user_return(self, frame, retval):
        print('+++ return', retval)
    def user_exception(self, frame, exc_stuff):
        print('+++ exception', exc_stuff)
        self.set_continue()
        
class BaseDebuggerTestCase(unittest.TestCase):
    """This is basically the Test Case that comes with bdb, but changed to
    unittest format"""
    def setUp(self):
        pass
    
    def runTest(self):
        code = [
            "import epdblib.basedebugger",
            #"import couchdb",
            "def bar(a):",
            "    print('bar(', a, ')')",
            "    return a/2",
            "",
            "def foo(n):",
            "    print('foo(', n, ')')",
            "    x = bar(n*10)",
            "    print('bar returned', x)",
            "foo(10)",
        ]
        code = "\n".join(code)
        t = Tdb()
        t.run(code)
        print("calls:", t.calls)

    def tearDown(self):
        pass

class CanonicTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.basedebugger' in sys.modules:
            del sys.modules['epdblib.basedebugger']
        import epdblib.basedebugger
        dbg = epdblib.basedebugger.BaseDebugger()
        self.assertEqual(dbg.canonic("<string>"), "<string>")
        self.assertEqual(dbg.canonic("/usr/lib"), "/usr/lib")
        
if __name__ == '__main__':
    unittest.main()
