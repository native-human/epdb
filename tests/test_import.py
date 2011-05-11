from coverage import coverage
from helpers import CoverageTestCase
import epdblib.importer
import unittest
import sys
import imp

class PrintImportHook:
    def __init__(self, path=None):
        pass

    def find_module(self, fullname, path=None):
        print("[PrintHook]", fullname)
        return None

class DebuggerStub:
    def __init__(self):
        self.skip = set([])

    def add_skip_module(self, module):
        self.skip.add(module)

class ImportImportingTestCase(CoverageTestCase):
    def runTest(self):
        if 'epdblib.importer' in sys.modules:
            del sys.modules['epdblib.importer']
        import epdblib.importer

class ImportTestCase(CoverageTestCase):
    def setUp(self):
        self.dbg = DebuggerStub()
        
        CoverageTestCase.setUp(self)
        
        sys.meta_path.append(epdblib.importer.EpdbImportFinder(debugger=self.dbg, dbgmods=['./dbgmods']))
        sys.meta_path.append(PrintImportHook())

    def tearDown(self):
        CoverageTestCase.tearDown(self)
        del sys.meta_path[:]

class PatchRandomTestCase(ImportTestCase):
    def test_patch_random(self):
        import random
        imp.reload(random)
        t = random.randint(1,2)
        self.assertEqual(t, 42)
        self.assertIn('random', self.dbg.skip)

class PatchRandomFromTestCase(ImportTestCase):
    def test_patch_random_from(self):
        if 'random' in sys.modules.keys():
            del sys.modules['random']
        from random import randint
        t = randint(1,2)
        self.assertEqual(t, 42)
        self.assertIn('random', self.dbg.skip)

class PatchSubmodulesTestCase(ImportTestCase):
    def test_patch_spam_ham(self):
        import spam.eggs.ham
        self.assertEqual(42, spam.eggs.ham.hello_world())
        self.assertIn('spam.eggs.ham', self.dbg.skip)

class ImportTestCase(ImportTestCase):
    def test_builtins(self):
        if 'builtins' in sys.modules.keys():
            del sys.modules['builtins']
        import builtins
        self.assertEqual(builtins.dir(), "patched dir")

if __name__ == '__main__':
    unittest.main()
