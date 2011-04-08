import unittest
from coverage import coverage
import inspect
import os

class CoverageTestCase(unittest.TestCase):
    def setUp(self):
        print(inspect.getmodule(self).__file__)
        filename = ".coverage." + os.path.basename(inspect.getmodule(self).__file__) + "." + self.__class__.__name__
        self.cov = coverage(data_file=filename, source=["epdblib"], cover_pylib=True)
        self.cov.start()
        
    def tearDown(self):
        self.cov.stop()
        self.cov.save()