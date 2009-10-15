#!/usr/bin/env python

import os
import signal
import multiprocessing
import sys

def conthandler(num, frame):
    print('continue')

signal.signal(signal.SIGCONT, conthandler)

class Savepoint:
    def __init__(self):
        self.queue = multiprocessing.Queue()
        pid = os.fork()
        self.pid = pid
        if pid:
            # Parent
            pass
        else:
            # Child
            while True:
                item = self.queue.get()
                if item == "close":
                    sys.exit(0)
                if item == "run":
                    print("Running not implemented yet")
                    break
    
    def run(self):
        self.queue.put("run")
    
class ControllerProcess:
    def __init__(self):
        self.queue = multiprocessing.Queue()
        pid = os.fork()
        if pid:
            while True:
                item = self.queue.get()
        else:
            pass
                
    def createsavepoint(self):
        self.queue.put("create")
        
    
class Savepoints:
    def __init__(self):
        pass

pid = None

def save():
    svp = Savepoint()
    #global pid
    #pid = os.fork()
    #if pid:
    #    # parent
    #    ""
    #else:
    #    # child
    #    print("child pause")
    #    signal.pause()
    #    print("child pause ended")
    
def restore():
    os.kill(pid, signal.SIGCONT)
    print("child restore")
    pass

def init():
    print("Pid: " + str(os.getpid()))
    q = multiprocessing.Queue()
    pid = os.fork()
    if pid:
        # parent, controlling process
        pass
    else:
        # child, executing process
        print("child pause")
        signal.pause()
        print("child pause ended")


#sys.exit(0)

#init()

print ("line1")
print ("line2")
svp = Savepoint()
#save()
print ("line3")
print ("line4")
svp.run()
#restore()
print("line5")

if pid:
    (cpid, status, rusage) = os.wait3(0)
    print(cpid, status, rusage)