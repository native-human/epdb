import epdblib.debugger
import epdb
import sys
import unittest
from coverage import coverage

class EpdbStub:
    def __init__(self, uds_file=None, dbgmods=[]):
        self.uds_file = uds_file
        self.dbgmods = dbgmods

class ArgumentTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_epdb_cls = epdblib.debugger.Epdb
        epdblib.debugger.Epdb = EpdbStub
        self.cov = coverage(source=['epdb', "epdblib"], cover_pylib=True)
        self.cov.start()

    def test_uds_file(self):
        dbg, mainpyfile = epdb.parse_args(['epdb.py', '--uds', '/tmp/test', 'testfile'])
        self.assertEqual(mainpyfile, 'testfile')
        self.assertEqual(dbg.uds_file, '/tmp/test')
        self.assertEqual(dbg.dbgmods, [''])

    def test_uds_file(self):
        dbg, mainpyfile = epdb.parse_args(['epdb.py', '--dbgmods', '/tmp/dbgmods', 'dbgfile'])
        self.assertEqual(mainpyfile, 'dbgfile')
        self.assertEqual(dbg.dbgmods, ['/tmp/dbgmods'])
        self.assertEqual(dbg.uds_file, None)

    def test_incorrect(self):
        self.assertRaises(epdb.UsageException,
                          epdb.parse_args, ['epdb.py', '--dbgmods'])
        self.assertRaises(epdb.UsageException,
                          epdb.parse_args, ['epdb.py', '--uds'])
        self.assertRaises(epdb.UsageException,
                          epdb.parse_args, ['epdb.py'])
    def tearDown(self):
        epdblib.debugger.Epdb = self._orig_epdb_cls
        self.cov.stop()
        self.cov.save()

if __name__ == '__main__':
    unittest.main()
