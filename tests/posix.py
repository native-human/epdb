#!/usr/bin/env python

#import posix_ipc
import os
import sys
import pickle

import ctypes
from ctypes import *

libc = cdll.LoadLibrary("libc.so.6")
print (libc.time(None))

#class Savepoint:
#    def __init__(self):
#        self.queue = multiprocessing.Queue()
#        pid = os.fork()
#        self.pid = pid
#        if pid:
#            # Parent
#            pass
#        else:
#            # Child
#            while True:
#                item = self.queue.get()
#                if item == "close":
#                    sys.exit(0)
#                if item == "run":
#                    print("Running not implemented yet")
#                    break
#    
#    def run(self):
#        self.queue.put("run")

class MainProcess:
    def __init__(self):
        self.start_main_process()
    
    def start_main_process(self):
        debugee_queue = posix_ipc.MessageQueue(None, posix_ipc.O_EXCL|posix_ipc.O_CREAT)
        pid = os.fork()
        if pid:
            # Controller Process
            while True:
                recv, prio = debugee_queue.receive()
                cmd,arg = pickle.loads(recv)
                if cmd == "end":
                    #print 'End'
                    debugee_queue.unlink()
                    debugee_queue.close()
                    sys.exit(0)
                else:
                    print(cmd, arg)
        else:
            # Debugee Process
            self.main_queue = main_queue = debugee_queue
            main_queue.send(pickle.dumps(("hello",None)))
            main_queue.send(pickle.dumps(("end",None)))
        
#class SavePoint:
#    def __init__(self, mainprocess):
#        self.queue = multiprocessing.Queue()
#        pid = os.fork()
#        self.pid = pid
#        if pid:
#            # Parent
#            pass
#        else:
#            # Child
#            while True:
#                item = self.queue.get()
#                if item == "close":
#                    sys.exit(0)
#                if item == "run":
#                    print("Running not implemented yet")
#                    break
#    

#mainprocess = MainProcess()

print("arg1")
print("arg2")
print("arg3")
#queue = posix_ipc.MessageQueue(None, posix_ipc.O_EXCL|posix_ipc.O_CREAT)
#
#print queue.name
#queue.send("hello")
#print queue.receive()
#
#queue.close()
#queue.unlink()