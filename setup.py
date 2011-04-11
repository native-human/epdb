from distutils.core import setup

setup(name='epdb',
      version='0.1',
      description='Extended Python Debugger',
      author='Patrick Sabin',
      author_email='patricksabin@gmx.at',
      url='http://code.google.com/p/epdb/',
      packages=['epdblib'],
      #scripts=['bin/epdb'],
      py_modules=['epdb']
      )
