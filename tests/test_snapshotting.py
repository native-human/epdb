import sys
import unittest
from coverage import coverage
import epdblib.snapshotting
import multiprocessing
import time
import epdblib.shareddict
import os
import atexit

def server_dummy(dofork=True):
    return

# monkey patch fork. Otherwise the child process would try to join everything
# TODO also make coverage of the child process
orig_fork = os.fork
def fork():
    pid = orig_fork()
    if not pid:
        atexit._clear()
    return pid

class SnapshottingTestCase(unittest.TestCase):
    def setUp(self):
        self.mp = epdblib.snapshotting.MainProcess(startserver=False)

        self.sd_process = multiprocessing.Process(target=self.shareddict_server_process, args=())
        self.sd_process.start()

        time.sleep(0.2)

        self.process = multiprocessing.Process(target=self.server_process, args=())
        self.process.start()

        self.cov = coverage(data_file=".coverage.snapshotting.client", source=["epdblib"], cover_pylib=True)
        self.cov.start()

    def shareddict_server_process(self):
        self.server = epdblib.shareddict.server(dofork=False)

    def server_process(self):
        self.cov = coverage(data_file=".coverage.snapshotting.server", source=["epdblib"], cover_pylib=True)
        self.cov.start()
        self.mp.server()
        #epdblib.snapshotting.shareddict.server = server_dummy
        #self.server = epdblib.snapshotting.MainProcess(startserver=False)
        #self.mp.server()
        self.cov.stop()
        self.cov.save()

    def tearDown(self):
        self.sd_process.join()
        self.process.join()
        self.cov.stop()
        self.cov.save()

    def test_snapshotting(self):
        if 'epdblib.snapshotting' in sys.modules:
            del sys.modules['epdblib.snapshotting']
            import epdblib.snapshotting
        epdblib.snapshotting.os.fork = fork
        self.mp.set_up_client()
        try:
            snapshot = self.mp.make_snapshot(0)
        except:
            sys.exit(0)
        self.mp.quit()
        epdblib.shareddict.shutdown()

if __name__ == '__main__':
    unittest.main()
