import sys
from helpers import CoverageTestCase
import unittest
from io import StringIO

class DictProxyMock(dict):
    def __init__(self, name, sockfile=None):
        dict.__init__(self)

class ListProxyMock(list):
    def __init__(self, name, sockfile=None):
        list.__init__(self)

class BreakpointTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.breakpoint' in sys.modules:
            del sys.modules['epdblib.breakpoint']
        
        import epdblib.shareddict
        epdblib.shareddict.DictProxy = DictProxyMock
        epdblib.shareddict.ListProxy = ListProxyMock
        from epdblib.breakpoint import Breakpoint
        
        b1 = Breakpoint("file1.py", 3)
        b2 = Breakpoint("file2.py", 4)
        
        queried_b1 = Breakpoint.bpbynumber[0]
        self.assertEqual(queried_b1, b1)
        self.assertNotEqual(queried_b1, b2)
        
        # TODO this raises an error
        #b2.deleteMe()
        b1.deleteMe()
        
        b1.bpprint(StringIO())
        
if __name__ == '__main__':
    unittest.main()
