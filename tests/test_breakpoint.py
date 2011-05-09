import sys
from helpers import CoverageTestCase
import unittest
from io import StringIO
import sys
import tempfile
import multiprocessing
from coverage import coverage
import epdblib.shareddict
import time
import shutil

class ImportTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.breakpoint' in sys.modules:
            del sys.modules['epdblib.breakpoint']
        import epdblib.breakpoint

class LocalBreakpointTestCase(CoverageTestCase):
    def runTest(self):
        from epdblib import breakpoint
        manager = breakpoint.LocalBreakpointManager()
        
        self.assertEqual(manager.breaks, {})
        self.assertEqual(manager.bplist, {})
        self.assertEqual(manager.bpbynumber, [None])
        self.assertFalse(manager.any_break_exists())
        
        bp1 = manager.new_breakpoint("file1", 10)
        
        self.assertEqual(manager.breaks["file1"], [10])
        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)

        # Create an breakpoint on the same new line
        bp2 = manager.new_breakpoint("file1", 10, cond="a=10")
        
        self.assertEqual(manager.breaks["file1"], [10])
        self.assertIn(bp2, manager.breakpoint_by_position('file1', 10))
        self.assertEqual(manager.breakpoint_by_number(bp2.number), bp2)

        bp2.enable()
        bp1.disable()
        manager.update(bp2)
        manager.update(bp1)
        bp2.delete()

        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)
        self.assertEqual(manager.breaks["file1"], [10])
        
        # test second Breakpoint in another file
        bp3 = manager.new_breakpoint("file2", 2, cond="a=10")
        
        self.assertEqual(manager.breaks["file2"], [2])
        self.assertIn(bp3, manager.breakpoint_by_position('file2', 2))
        self.assertEqual(manager.breakpoint_by_number(bp3.number), bp3)

        manager.clear_break('file2', 2)
        
        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)
        self.assertEqual(manager.breaks["file1"], [10])

        self.assertFalse(manager.file_has_breaks('file2'))
        self.assertTrue(manager.file_has_breaks('file1'))
        self.assertTrue(manager.any_break_exists())
        self.assertEqual(manager.get_file_breaks('file2'), [])
        
        frame = sys._getframe()
        lineno = frame.f_lineno
        funcname = frame.f_code.co_name
        bp_runTest = manager.new_breakpoint("test_breakpoint", lineno, funcname=funcname)
        self.assertIsNone(bp_runTest.func_first_executable_line)
        ret = manager.checkfuncname(bp_runTest, frame)
        self.assertTrue(ret)
        self.assertIsNotNone(bp_runTest.func_first_executable_line)
        
        ret = manager.checkfuncname(bp_runTest, frame)
        # No we are not at the beginning of the function
        self.assertFalse(ret)
        
        bp_runother = manager.new_breakpoint("test_breakpoint", lineno, funcname="runother")
        self.assertFalse(manager.checkfuncname(bp_runother, frame))
        
        bp_lineno = manager.new_breakpoint("test_breakpoint", 1)
        self.assertFalse(manager.checkfuncname(bp_lineno, frame))
        
        # Don't add any space between the next line
        bp_lineno2 = manager.new_breakpoint("test_breakpoint", frame.f_lineno+1) 
        self.assertTrue(manager.checkfuncname(bp_lineno2, frame))
        
        self.assertTrue(manager.file_has_breaks("test_breakpoint"))
        manager.clear_all_file_breaks("test_breakpoint")
        self.assertFalse(manager.file_has_breaks("test_breakpoint"))
        self.assertTrue(manager.any_break_exists())

        # First breakpoint not effective, because disabled
        bp_eff1 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname)
        bp_eff1.disable()
        # Second breakpoint not effective because cond evaluates to false
        bp_eff2 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="False")
        bp, flag = manager.effective("test_breakpoint", 10, frame)
        
        # Third evaluates to true but has ignore set to some value > 0
        bp_eff3 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="True")
        bp_eff3.ignore = 3
        
        # Fourth has now condition, but ignore > 0
        bp_eff4 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname)
        bp_eff4.ignore = 3
        
        # Fifth breakpoint is fine
        bp_eff5 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="True")
        
        bp, flag = manager.effective("test_breakpoint", 10, frame)
        self.assertEqual(bp, bp_eff5)
        
        manager.clear_all_file_breaks("test_breakpoint")
        
        # Sixth has an invalid condition effective should return it
        bp_eff6 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="xy><!z")
        bp, flag = manager.effective("test_breakpoint", 10, frame)
        
        self.assertEqual(bp, bp_eff6)
        
        manager.clear_all_breaks()
        self.assertFalse(manager.any_break_exists())

class SharedBreakpointTestCase(unittest.TestCase):
    def setUp(self):
        self.sock_dir = tempfile.mkdtemp(prefix="epdbtest-shared-")
        
        self.process = multiprocessing.Process(target=self.server_process, args=())
        self.process.start()
        time.sleep(0.2) # TODO Better synchronization
        
        self.cov = coverage(data_file=".coverage.breakpoint.shareddict.client",
                            source=["epdblib"],
                            cover_pylib=True)
        self.cov.start()
        
    def server_process(self):
        self.cov = coverage(data_file=".coverage.breakpoint.shareddict.server",
                            source=["epdblib"],
                            cover_pylib=True)
        self.cov.start()
        self.server = epdblib.shareddict.server(self.sock_dir,exitatclose=False)
        self.cov.stop()
        self.cov.save()

    def tearDown(self):
        epdblib.shareddict.shutdown(self.sock_dir)
        self.process.join(timeout=1)
        shutil.rmtree(self.sock_dir)
        self.cov.stop()
        self.cov.save()

    def runTest(self):
        from epdblib import breakpoint
        self.proxycreator = epdblib.shareddict.ProxyCreator(self.sock_dir)
        manager = breakpoint.BreakpointManager(self.proxycreator)
        
        self.assertEqual(manager.breaks, {})
        self.assertEqual(manager.bplist, {})
        self.assertEqual(manager.bpbynumber, [None])
        self.assertFalse(manager.any_break_exists())
        
        bp1 = manager.new_breakpoint("file1", 10)
        
        self.assertEqual(manager.breaks["file1"], [10])
        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)

        # Create an breakpoint on the same new line
        bp2 = manager.new_breakpoint("file1", 10, cond="a=10")
        
        self.assertEqual(manager.breaks["file1"], [10])
        self.assertIn(bp2, manager.breakpoint_by_position('file1', 10))
        self.assertEqual(manager.breakpoint_by_number(bp2.number), bp2)

        bp2.enable()
        bp1.disable()
        manager.update(bp2)
        manager.update(bp1)
        bp2.delete()

        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)
        self.assertEqual(manager.breaks["file1"], [10])
        
        # test second Breakpoint in another file
        bp3 = manager.new_breakpoint("file2", 2, cond="a=10")
        
        self.assertEqual(manager.breaks["file2"], [2])
        self.assertIn(bp3, manager.breakpoint_by_position('file2', 2))
        self.assertEqual(manager.breakpoint_by_number(bp3.number), bp3)

        manager.clear_break('file2', 2)
        
        self.assertEqual(manager.breakpoint_by_position('file1', 10), [bp1])
        self.assertEqual(manager.breakpoint_by_number(bp1.number), bp1)
        self.assertEqual(manager.breaks["file1"], [10])

        self.assertFalse(manager.file_has_breaks('file2'))
        self.assertTrue(manager.file_has_breaks('file1'))
        self.assertTrue(manager.any_break_exists())
        self.assertEqual(manager.get_file_breaks('file2'), [])
        
        frame = sys._getframe()
        lineno = frame.f_lineno
        funcname = frame.f_code.co_name
        bp_runTest = manager.new_breakpoint("test_breakpoint", lineno, funcname=funcname)
        self.assertIsNone(bp_runTest.func_first_executable_line)
        ret = manager.checkfuncname(bp_runTest, frame)
        self.assertTrue(ret)
        self.assertIsNotNone(bp_runTest.func_first_executable_line)
        
        ret = manager.checkfuncname(bp_runTest, frame)
        # No we are not at the beginning of the function
        self.assertFalse(ret)
        
        bp_runother = manager.new_breakpoint("test_breakpoint", lineno, funcname="runother")
        self.assertFalse(manager.checkfuncname(bp_runother, frame))
        
        bp_lineno = manager.new_breakpoint("test_breakpoint", 1)
        self.assertFalse(manager.checkfuncname(bp_lineno, frame))
        
        # Don't add any space between the next line
        bp_lineno2 = manager.new_breakpoint("test_breakpoint", frame.f_lineno+1) 
        self.assertTrue(manager.checkfuncname(bp_lineno2, frame))
        
        self.assertTrue(manager.file_has_breaks("test_breakpoint"))
        manager.clear_all_file_breaks("test_breakpoint")
        self.assertFalse(manager.file_has_breaks("test_breakpoint"))
        self.assertTrue(manager.any_break_exists())

        # First breakpoint not effective, because disabled
        bp_eff1 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname)
        bp_eff1.disable()
        manager.update(bp_eff1)
        
        # Second breakpoint not effective because cond evaluates to false
        bp_eff2 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="False")
        manager.update(bp_eff2)
       
        bp, flags = manager.effective("test_breakpoint", 10, frame)
        
        # Third evaluates to true but has ignore set to some value > 0
        bp_eff3 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="True")
        bp_eff3.ignore = 3
        manager.update(bp_eff3)
        
        # Fourth has now condition, but ignore > 0
        bp_eff4 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname)
        bp_eff4.ignore = 3
        manager.update(bp_eff4)
        
        # Fifth breakpoint is fine
        bp_eff5 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="True")
        
        bp, flag = manager.effective("test_breakpoint", 10, frame)
        self.assertEqual(bp, bp_eff5)
        
        manager.clear_all_file_breaks("test_breakpoint")
        
        # Sixth has an invalid condition effective should return it
        bp_eff6 = manager.new_breakpoint("test_breakpoint", 10, funcname=funcname, cond="xy><!z")
        bp, flag = manager.effective("test_breakpoint", 10, frame)
        
        self.assertEqual(bp, bp_eff6)
        
        manager.clear_all_breaks()
        self.assertFalse(manager.any_break_exists())

if __name__ == '__main__':
    unittest.main()
