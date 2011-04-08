import sys
import unittest
from helpers import CoverageTestCase
from epdblib import dbg
import epdblib.debugger

class ComMock:
    def __init__(self):
        self.called_functions = []

class MainProcessMock:
    def __init__(self):
        dbg.timelines = TimelinesProxyMock()
        dbg.current_timeline = TimelineProxyMock()
        name = 'head'
        dbg.timelines.set_current_timeline(name)
        dbg.nde = DictProxyMock('nde.head')
        
class TimelineProxyMock:
    def __init__(self):
        pass
   
    def new_resource(self, type, location):
        pass
   
    def create_manager(self, identification, manager):
        return ManagerMock()
   
    def get_resource(self, type, location):
        return DictProxyMock("resource")
   
    def get_max_ic(self):
        return 10
    
    def get_next(self):
        return {}
   
class ManagerMock:
    def __init__(self):
        pass
    
    def save(self):
        pass
   
class TimelinesProxyMock:
    def __init__(self):
        print("TimelinesProxyMock")
    
    def set_current_timeline(self, name):
        pass

class DictProxyMock(dict):
    def __init__(self, objref, conn=None):
        dict.__init__(self)

class DebuggerTestCase(CoverageTestCase):
    def setUp(self):  
        import epdblib.debugger
        import epdblib.snapshotting
        import epdblib.dbg
        epdblib.snapshotting.MainProcess = MainProcessMock
        epdblib.shareddict.DictProxy = DictProxyMock
        CoverageTestCase.setUp(self)
        self.epdb = epdblib.debugger.Epdb()


class NavigationCmdTestCase(DebuggerTestCase):
    def findnextbreakpointic(self):
        return -1
    
    def findsnapshot(self, maxic):
        snapshotdata = epdblib.debugger.SnapshotData(id=0, ic=0) 
        return snapshotdata
    
    def setUp(self):
        DebuggerTestCase.setUp(self)
        # mock findnextbreakpointic
        self.epdb.findnextbreakpointic = self.findnextbreakpointic
        self.epdb.findsnapshot = self.findsnapshot

class ContinueTestCase(NavigationCmdTestCase):
    def test_continue(self):
        r = self.epdb.cmd_continue("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "continue")
        
        dbg.mode = "redo"
        r = self.epdb.cmd_continue("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "continue")

class StepTestCase(NavigationCmdTestCase):
    def test_step(self):
        r = self.epdb.cmd_step("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "step")
        
        dbg.mode = "redo"
        r = self.epdb.cmd_step("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "step")


class NextTestCase(NavigationCmdTestCase):
    def test_next(self):
        self.epdb.curframe = "test" # XXX: need this to make the test work
        
        r = self.epdb.cmd_next("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "next")
        
        dbg.mode = "redo"
        r = self.epdb.cmd_next("")
        self.assertEqual(r, 1)
        self.assertEqual(self.epdb.running_mode, "next")

  
class DebuggerImportingTestCase(DebuggerTestCase):
    def test_importing(self):
        if 'epdblib.debugger' in sys.modules:
            del sys.modules['epdblib.debugger']
        import epdblib.debugger
                
if __name__ == '__main__':
    unittest.main()
