#!/usr/bin/env python

import os
import sys

r,w = os.pipe()

class MainProcess:
    def __init__(self):
        self.start_main_process()

    def start_main_process(self):
        read_end, write_end = os.pipe()
        pid = os.fork()
        if pid:
            # Controller Process
            debuggee_pipe = os.fdopen(read_end)
            while True:
                line = debuggee_pipe.readline()
                words = line.rstrip().split(" ")
                cmd = words[0]
                if cmd == "end":
                    #print 'End'
                    sys.exit(0)
                if cmd == 'pipe':
                    arg = int(words[1])
                    print arg
                    sp1 = os.fdopen(arg, 'w')
                    sp1.write('wakeup\n')
                    sp1.flush()
                else:
                    print(cmd)
        else:
            # Debugee Process
            controller_pipe = os.fdopen(write_end, 'w')
            controller_pipe.write("hello\n")
            controller_pipe.flush()

            sp_r, sp_w = os.pipe()
            print(sp_r,sp_w)
            controller_pipe.write('pipe {0}\n'.format(sp_w))
            controller_pipe.flush()

            sp1 = os.fdopen(sp_r, 'r')
            print sp1.readline()

            controller_pipe.write("end\n")
            controller_pipe.flush()

MainProcess()
