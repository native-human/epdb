#from distutils.core import setup
from setuptools import setup

setup(name='epdb',
      version='0.1rc1',
      description='Extended Python Debugger',
      author='Patrick Sabin',
      author_email='patricksabin@gmx.at',
      url='http://code.google.com/p/epdb/',
      packages=['epdblib'],
      scripts=['scripts/epdb'],
      py_modules=['epdb'],
      classifiers=[
      'Development Status :: 4 - Beta',
      'Programming Language :: Python :: 3',
      'Intended Audience :: Developers',
      ]
      )
