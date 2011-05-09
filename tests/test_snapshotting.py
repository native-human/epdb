import sys
import unittest
from coverage import coverage
import epdblib.snapshotting
import multiprocessing
import time
import epdblib.shareddict
from epdblib import dbg
import os
import atexit
import tempfile
import shutil
import traceback
from helpers import CoverageTestCase

def server_dummy(dofork=True):
    return

# monkey patch fork. Otherwise the child process would try to join everything
# TODO also make coverage of the child process
orig_fork = os.fork
def fork():
    pid = orig_fork()
    if not pid:
        print("patched fork")
        atexit._clear()
    return pid

class ImportTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.snapshotting' in sys.modules:
            del sys.modules['epdblib.snapshotting']
        import epdblib.snapshotting

class SnapshottingTestCase(unittest.TestCase):
    def setUp(self):
        self.sock_dir = tempfile.mkdtemp(prefix="epdbtest-snap-")
        #sockfile = os.path.join(SOCK_DIR, 'shareddict.sock')
        #self.sockfile = sockfile
        #dbg.shareddict_sock = self.sockfile
        
        self.sd_process = multiprocessing.Process(target=self.shareddict_server_process, args=())
        self.sd_process.start()
        
        time.sleep(0.2)
        
        self.proxycreator = epdblib.shareddict.ProxyCreator(self.sock_dir)
        self.mp = epdblib.snapshotting.MainProcess(self.proxycreator, startserver=False)

        self.process = multiprocessing.Process(target=self.server_process, args=())
        self.process.start()

        time.sleep(0.2)

        self.cov = coverage(data_file=".coverage.snapshotting.client", source=["epdblib"], cover_pylib=True)
        self.cov.start()

    def shareddict_server_process(self):
        self.cov = coverage(data_file=".coverage.snapshotting.shareddict.server", source=["epdblib"], cover_pylib=True)
        self.cov.start()
        self.server = epdblib.shareddict.server(self.sock_dir,
                                                dofork=False,
                                                exitatclose=False)
        self.cov.stop()
        self.cov.save()

    def server_process(self):
        self.cov = coverage(data_file=".coverage.snapshotting.server", source=["epdblib"], cover_pylib=True)
        self.cov.start()
        
        #import epdblib.shareddict
        #import epdblib.debug
        #import epdblib.snapshotting
        #self.mp.server()
        #epdblib.snapshotting.shareddict.server = server_dummy
        #self.server = epdblib.snapshotting.MainProcess(startserver=False)
        self.mp.server()
        self.cov.stop()
        self.cov.save()

    def tearDown(self):
        self.mp.quit()
        
        epdblib.shareddict.shutdown(self.sock_dir)
        
        self.sd_process.join()
        self.process.join()
        
        #shutil.rmtree(self.sock_dir)
        self.cov.stop()
        self.cov.save()
        #print("TEAR DOWN END")
    
    def test_snapshotting(self):
        epdblib.snapshotting.os.fork = fork
        self.mp.set_up_client()
        
        try:
            snapshot = self.mp.make_snapshot(0)
            pass
        except:
            #exctype,exc,tb = sys.exc_info()
            #print(exctype, exc)
            #traceback.print_tb(tb)
            #print("snapshot pid", os.getpid())
            sys.exit(0)

if __name__ == '__main__':
    unittest.main()
