import sys
import unittest
from coverage import coverage
import epdblib.shareddict
import multiprocessing
import time
import tempfile
import os
import shutil
from epdblib import dbg
from helpers import CoverageTestCase

class ImportTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.shareddict' in sys.modules:
            del sys.modules['epdblib.shareddict']
        import epdblib.shareddict

class ShareddictTestCase(unittest.TestCase):
    def setUp(self):
        self.sock_dir = tempfile.mkdtemp(prefix="epdbtest-shared-")
        
        self.process = multiprocessing.Process(target=self.server_process, args=())
        self.process.start()
        time.sleep(0.2) # TODO Better synchronization
        
        self.cov = coverage(data_file=".coverage.shareddict.client",
                            source=["epdblib"],
                            cover_pylib=True)
        self.cov.start()
        
    def server_process(self):
        self.cov = coverage(data_file=".coverage.shareddict.server",
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
    
    def test_timelinesproxy_new(self):
        proxycreator = epdblib.shareddict.ProxyCreator(self.sock_dir)
        #timelines = epdblib.shareddict.TimelinesProxy("timelines", sockfile=self.sockfile)
        timelines = proxycreator.create_timelines("timelines")
        current_timeline = timelines.new_timeline()
        name = current_timeline.get_name()
        self.assertEqual(name, "head")
        timelines.set_current_timeline(name)
        nde = current_timeline.get_nde()
        timelines.close()

    def test_dictproxy_new(self):
        proxycreator = epdblib.shareddict.ProxyCreator(self.sock_dir)
        #timelines = epdblib.shareddict.TimelinesProxy("timelines", sockfile=self.sockfile)
        d = proxycreator.create_dict("breaks")
        d["hallo"] = "Welt"
        d.close()
    

    #@unittest.skip
    #def test_timelinesproxy(self):
    #    if 'epdblib.shareddict' in sys.modules:
    #        del sys.modules['epdblib.shareddict']
    #        import epdblib.shareddict
    #    timelines = epdblib.shareddict.TimelinesProxy("timelines", sockfile=self.sockfile)
    #    current_timeline = timelines.new_timeline()
    #    name = current_timeline.get_name()
    #    self.assertEqual(name, "head")
    #    timelines.set_current_timeline(name)
    #    nde = current_timeline.get_nde()
    #
    #    epdblib.shareddict.shutdown(self.sockfile)
    #    self.process.join(timeout=1)
    
if __name__ == '__main__':
    unittest.main()
