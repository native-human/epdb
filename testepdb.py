

import sys
import pexpect
import re
import argparse

class DbgAnswer:
    def __init__(self, ic=None, mode=None, timeout=False):
        self.ic = None
        self.mode = None
        self.timeout = timeout
        self.line = None
        self.lineno = None

class TestClass:
    def debuggee_send(self, line=None):
        if line:
            if not line.endswith('\n'):
                line += '\n'
            self.debuggee.send(line)
        dbganswer = DbgAnswer()
        try:
            i = 0
            while True:
                line = self.debuggee.readline()
                linem = re.match('> ([<>/a-zA-Z0-9_\.]+)\(([0-9]+)\).*', line)
                icm = re.match("#ic: (\d+) mode: (\w+)", line)
                if line.startswith('(Pdb)') or line.startswith('(Epdb)'):
                    break
                elif icm:
                    ic = icm.group(1)
                    mode = icm.group(2)
                    dbganswer.ic = ic
                    dbganswer.mode = mode
                elif line.startswith("->"):
                    dbganswer.line = line[3:]
                elif linem:
                    if linem.group(1) == '<string>':
                        continue
                    lineno = int(linem.group(2))
                    dbganswer.lineno = lineno
        except pexpect.TIMEOUT:
            dbganswer.timeout = False
        return dbganswer

    def test_comprehensions(self):
        self.debuggee = pexpect.spawn("python3 -m epdb testprograms/listcomprehension.py", timeout=30)
        a = self.debuggee_send()
        assert(a.lineno == 3)
        a = self.debuggee_send('next')
        assert(a.timeout == False)
        assert(a.ic == '202') # TODO here is some weired behavior of pdb (and therefore epdb)
        assert(a.mode == 'normal')
        assert(a.lineno == 5)


tc = TestClass()
tc.test_comprehensions()
