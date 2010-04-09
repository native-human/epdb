#!/usr/bin/env python

import socket
import os
import sys
import select
import logging

SOCK_NAME = "/tmp/socketname"

log = logging.getLogger('socket.test')
log.addHandler(logging.StreamHandler(sys.stderr))
log.setLevel(logging.DEBUG)
    
class Savepoint:
    def __init__(self):
        #log.info('Savepoint fork')
        #log.info('parentpid: %d %d' % (pid, os.getpid()))
        
        # This is done before forking because of synchronization
        self.cpids = []
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCK_NAME)
        sck = Mysocket(s)
        sck.mysend('savepoint')
        if sck.myrecv() != 'ok':
            # TODO better Error handling
            raise Exception()
        
        pid = os.fork()
        self.pid = pid
        if pid:
            # Parent
            self.cpids.append(pid)
            while True:
                item = sck.myrecv()
                if item == "close":
                    #log.info('Savepoint quit ... Wait for subprocess')
                    while self.cpids != []:
                        (pid,status) = os.wait()
                        idx = self.cpids.index(pid)
                        del self.cpids[idx]
                    #log.info('Savepoint quit')
                    sys.exit(0)
                if item == "run":
                    rpid = os.fork()
                    if rpid:
                        self.cpids.append(rpid)
                    else:    
                        #log.info("Child process runs")
                        break
        else:
            log.info('childpid %d'% pid)
            pass
    
class Mysocket:
    def __init__(self, sock=None):
        self.MSG_LEN = 15
        if sock is None:
            self.sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
    def connect(self,host, port):
        self.sock.connect((host, port))
    def mysend(self, msg):
        if hasattr(msg, 'encode'):
            msg = msg.encode('ascii')
        if len(msg) > self.MSG_LEN:
            raise RuntimeError("msg is too long")
        if len(msg) < self.MSG_LEN:
            trail = b'\n' * (self.MSG_LEN - len(msg))
            msg = msg + trail
            
        #log.info('____')
        #log.info(msg)
        #log.info('____')
        totalsent = 0
        while totalsent < self.MSG_LEN:
            sent = self.sock.send(msg[totalsent:])
            #print('sent successfull ' + str(sent))
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
            
    def myrecv(self):
        msg = b''
        while len(msg) < self.MSG_LEN:
            chunk = self.sock.recv(self.MSG_LEN-len(msg))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
            # print('recv', len(chunk), len(msg))
        msg = msg.decode('ascii')
        return msg.rstrip()
    def close(self):
        self.sock.close()



class SavepointConnection:
    def __init__(self, mysocket):
        self.mysocket = mysocket
    
    def respond(self):
        cmd = self.mysocket.myrecv()
        logging.info('cmd')
    
    def activate(self):
        self.mysocket.mysend('run')
    
    def quit(self):
        self.mysocket.mysend('close')

class MainProcess:
    def __init__(self):
        #log.info("start process")
        debuggee_sock, controller_sock = socket.socketpair()
        debuggee = Mysocket(debuggee_sock)
        self.debuggee = debuggee
        controller = Mysocket(controller_sock)
        backupcontroller = controller # TODO remove
        sp_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sp_sock.bind(SOCK_NAME)
        #log.info("bound")
        sp_sock.listen(10)
        self.savepoint_connections = []
        self.do_quit = False
        pid = os.fork()
        if pid:
            p = select.poll()
            #log.info('Socket: %s' % controller.sock)
            p.register(controller.sock, select.POLLIN|select.POLLPRI)
            p.register(sp_sock, select.POLLIN|select.POLLPRI)
            while True:
                list = p.poll(100)
                if list == []:
                    if self.do_quit:
                        os.waitpid(pid,0)
                        os.unlink(SOCK_NAME)
                        #log.info('control quit')
                        sys.exit(0)
                for event in list:
                    fd, ev = event
                    
                    # Controller Code
                    
                    if fd == controller.sock.fileno():
                        #log.info('controller fd: %d' % controller.sock.fileno())
                        line = controller.myrecv()
                        #log.info('line: %s:' % line)
                        words = line.rstrip().split(" ")
                        cmd = str(words[0])
                        #log.info('cmd: "%s"' % cmd)
                        if cmd == "end":
                            #log.info('end received')
                            for conn in self.savepoint_connections:
                                #log.info("quit sent")
                                conn.quit()
                            self.do_quit = True
                            #os.unlink(SOCK_NAME)
                            #sys.exit(0)
                        if cmd == 'connect':
                            #log.info("connect received")
                            arg = words[1]
                            controller.mysend("Connected " + arg)
                        if cmd == 'showlist':
                            log.info('Len: %d' % len(self.savepoint_connections))
                        if cmd == 'activate':
                            #log.info("ACTIVATE")
                            arg = int(words[1])
                            #log.info("activate %d"%arg)
                            sp = self.savepoint_connections[arg]
                            sp.activate()
                        else:
                            log.info(cmd)
                            
                    # New Savepoint/Debuggee Connection
                    elif fd == sp_sock.fileno():
                        #log.info('new connection')
                        conn, addr = sp_sock.accept()
                        sock = Mysocket(conn)
                        type = sock.myrecv()
                        if type == 'savepoint':
                            sp = SavepointConnection(sock)
                            self.savepoint_connections.append(sp)
                            sock.mysend('ok')
                            #log.info('savepoint added')
                            if self.do_quit:
                                sp.quit()
                        
                        elif type == 'debuggee':
                            # TODO remove
                            pass
                            #log.info("New Debuggee")
                        else:
                            log.info("Critical Error")
                    else:
                        for conn in self.savepoint_connections:
                            if fd == conn.mysocket.sock.fileno():
                                conn.respond()
                                break
                        else:
                            #got = backupcontroller.myrecv()
                            #log.info("Additionally got: %s" % got)
                            log.info('Unknown fd: %s' % fd)
                            os.unlink(SOCK_NAME)
                            sys.exit(0)
        else:
            pass
    
    def list_savepoints(self):
        self.debuggee.mysend('showlist')
    
    def quit(self):
        self.debuggee.mysend('end')
        
    def activatesp(self, idx=0):
        # TODO idx
        self.debuggee.mysend('activate 0')
        self.debuggee.close()
        sys.exit(0)
        
      
mp = MainProcess()
 
log.info("line1")
log.info("Create Savepoint")
sp1 = Savepoint()
log.info("Savepoint created")
log.info("line2") 

mp.list_savepoints()

skip = input('>> Activate Sp? ')
if skip != 'True':
    log.info('>> Activate')
    mp.activatesp()
log.info('Skipped: "%s"'%skip)
#mp.list_savepoints()
 
log.info('last') 
 
#log.info('Show list')
#mp.list_savepoints() 

mp.quit()

log.info('main quit')
sys.exit(0)
