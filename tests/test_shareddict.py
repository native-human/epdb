import sys
import unittest
from coverage import coverage
import epdblib.shareddict
import multiprocessing
import time
import tempfile
import os
from epdblib import dbg

class ShareddictTestCase(unittest.TestCase):
    def setUp(self):
        SOCK_DIR = tempfile.mkdtemp(prefix="epdbtest-")
        sockfile = os.path.join(SOCK_DIR, 'shareddict.sock')
        self.sockfile = sockfile
        
        self.process = multiprocessing.Process(target=self.server_process, args=())
        self.process.start()
        time.sleep(0.2) # TODO Better synchronization
        
        self.cov = coverage(data_file=".coverage.shareddict.client", source=["epdblib"], cover_pylib=True)
        self.cov.start()
        
    def server_process(self):
        self.cov = coverage(data_file=".coverage.shareddict.server", source=["epdblib"], cover_pylib=True)
        self.cov.start()
        self.server = epdblib.shareddict.server(self.sockfile)
        self.cov.stop()
        self.cov.save()

    def tearDown(self):
        self.cov.stop()
        self.cov.save()
        
    def test_timelinesproxy(self):
        if 'epdblib.shareddict' in sys.modules:
            del sys.modules['epdblib.shareddict']
            import epdblib.shareddict
        timelines = epdblib.shareddict.TimelinesProxy("timelines", sockfile=self.sockfile)
        current_timeline = timelines.new_timeline()
        name = current_timeline.get_name()
        self.assertEqual(name, "head")
        timelines.set_current_timeline(name)
        nde = current_timeline.get_nde()

        epdblib.shareddict.shutdown(self.sockfile)
        self.process.join(timeout=1)
        
if __name__ == '__main__':
    unittest.main()
