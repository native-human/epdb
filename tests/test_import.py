from coverage import coverage
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

class NormalImportTestCase(unittest.TestCase):
    def setUp(self):
        self.dbg = DebuggerStub()
        sys.meta_path.append(epdblib.importer.EpdbImportFinder(debugger=self.dbg, dbgmods=['./dbgmods']))
        sys.meta_path.append(PrintImportHook())
        self.cov = coverage(source=["epdblib"], cover_pylib=True)
        self.cov.start()

    def test_patch_random(self):
        print('\n')
        import random
        imp.reload(random)
        t = random.randint(1,2)
        self.assertEqual(t, 42) 
        self.assertIn('random', self.dbg.skip)

    def test_patch_random_from(self):
        print('\n')
        if 'random' in sys.modules.keys():
            del sys.modules['random']
        from random import randint
        t = randint(1,2)
        self.assertEqual(t, 42) 
        self.assertIn('random', self.dbg.skip)

    def test_patch_spam_ham(self):
        print('\n')
        import spam.eggs.ham
        self.assertEqual(42, spam.eggs.ham.hello_world())
        self.assertIn('spam.eggs.ham', self.dbg.skip)
        
    def test_builtins(self):
        print('\n')
        if 'builtins' in sys.modules.keys():
            del sys.modules['builtins']
        import builtins
        self.assertEqual(builtins.dir(), "patched dir")
        
    def tearDown(self):
        self.cov.stop()
        self.cov.save()
        del sys.meta_path[:]

if __name__ == '__main__':
    unittest.main()
