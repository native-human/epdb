#!/usr/bin/env python

import multiprocessing
import os
from multiprocessing import Process, Value, Array


pipe1 = multiprocessing.Pipe()
(p1parent,p1child) = pipe1

pid = os.fork()
if pid:
    p1child.close()
    while True:
        try:
            item = p1parent.recv()
            print(item)
        except EOFError:
            break
    #while True:
    #    item = p1parent.recv()
    #    item = cmd, arg
    #
    #    if cmd == 'newpipe':
    #        pipe2 = arg
    #        p2parent, p2child = pipe2
    #        p2child.close()
    #        p2parent.send('hello')

else:
    p1parent.close()
    pipe2 = multiprocessing.Pipe()
    p2parent,p2child = pipe2
    p1child.send(pipe2)
    p1child.send('blup')
    #p2parent.close()
    #print(p2child.recv())
