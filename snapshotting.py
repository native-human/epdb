#!/usr/bin/env python

import socket
import os
import sys
import select
import logging
import tempfile

log = logging.getLogger('socket.test')
log.addHandler(logging.StreamHandler(sys.stderr))
log.setLevel(logging.DEBUG)

tmpfd, tmppath = tempfile.mkstemp(".dbg")
log.info("tmppath: " + tmppath)

SOCK_DIR = tempfile.mkdtemp()

SOCK_NAME = os.path.join(SOCK_DIR, 'debug')
#SOCK_NAME = tmppath

class SnapshotExit(Exception):
    """Raised when the controller process exits"""
    pass

class ControllerExit(Exception):
    """Raised when the controller process exits"""
    pass


class Snapshot:
    def __init__(self, ic, psnapshot):
        #log.info('Savepoint fork')
        #log.info('parentpid: %d %d' % (pid, os.getpid()))
        self.ic = ic
        self.psnapshot = psnapshot
        # This is done before forking because of synchronization
        self.cpids = []
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCK_NAME)
        msging = Messaging(s)
        msging.send('savepoint {0} {1}'.format(self.ic, psnapshot))
        msg = msging.recv()
        args = msg.split(' ')
        cmd = args[0]
        self.id = int(args[1])
        log.info("Made a snapshot with id {0}".format(self.id))
        if cmd != 'ok':
            # TODO better Error handling
            raise Exception()
        
        pid = os.fork()
        self.pid = pid
        if pid:
            # Parent
            self.cpids.append(pid)
            while True:
                item = msging.recv()
                if item == "close":
                    #log.info('Savepoint quit ... Wait for subprocess')
                    while self.cpids != []:
                        (pid,status) = os.wait()
                        idx = self.cpids.index(pid)
                        del self.cpids[idx]
                    #log.info('Savepoint quit')
                    raise SnapshotExit()
                    # sys.exit(0)
                if item == "run":
                    rpid = os.fork()
                    if rpid:
                        self.cpids.append(rpid)
                    else:    
                        #log.info("Child process runs")
                        break
        else:
            #log.info('childpid %d'% pid)
            pass
        
class Messaging:
    """This is wrapper around sockets, which allow to send and receive fixed
    length messages"""
    def __init__(self, sock=None):
        self.MSG_LEN = 30
        if sock is None:
            self.sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
    def connect(self,host, port):
        self.sock.connect((host, port))
    def send(self, msg):
        if hasattr(msg, 'encode'):
            msg = msg.encode('ascii')
        if len(msg) > self.MSG_LEN:
            raise RuntimeError("msg is too long")
        if len(msg) < self.MSG_LEN:
            trail = b'\n' * (self.MSG_LEN - len(msg))
            msg = msg + trail
            
        totalsent = 0
        while totalsent < self.MSG_LEN:
            sent = self.sock.send(msg[totalsent:])
            #print('sent successfull ' + str(sent))
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
            
    def recv(self):
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
    def __init__(self, msging, id, ic, psnapshot):
        self.msging = msging
        self.id = id
        self.ic = ic
        self.psnapshot = psnapshot
    
    def respond(self):
        cmd = self.msging.recv()
        logging.info('cmd')
    
    def activate(self):
        self.msging.send('run')
    
    def quit(self):
        self.msging.send('close')
        
class MainProcess:
    """This class forks the controller process. The controller process ends up
    in a loop. The other process returns with a connection to the controller"""
    def __init__(self):
        #log.info("start process")
        debuggee_sock, controller_sock = socket.socketpair()
        debuggee = Messaging(debuggee_sock)
        self.debuggee = debuggee
        controller = Messaging(controller_sock)
        backupcontroller = controller # TODO remove
        sp_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sp_sock.bind(SOCK_NAME)
        #log.info("bound")
        sp_sock.listen(10)
        self.savepoint_connections = []
        self.do_quit = False
        pid = os.fork()
        if pid:
            max_id = 0
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
                        line = controller.recv()
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
                        elif cmd == 'connect':
                            #log.info("connect received")
                            arg = words[1]
                            controller.send("Connected " + arg)
                        elif cmd == 'showlist':
                            log.info('ID           InstructionNr    PSnapshot')
                            log.info('----------------------------')
                            for s in self.savepoint_connections:
                                log.info("{0}    {1}     {2}".format(s.id, s.ic, s.psnapshot))
                            log.info('Number of snapshots: %d' %
                                     len(self.savepoint_connections))
                            controller.send('ok')
                        elif cmd == 'activate':
                            #log.info("ACTIVATE")
                            arg = int(words[1])
                            #log.info("activate %d"%arg)
                            for s in self.savepoint_connections:
                                if s.id == arg:
                                    sp = s
                                    break
                            sp = self.savepoint_connections[arg]
                            sp.activate()
                        else:
                            log.info(cmd)
                            
                    # New Savepoint/Debuggee Connection
                    elif fd == sp_sock.fileno():
                        #log.info('new connection')
                        conn, addr = sp_sock.accept()
                        msging = Messaging(conn)
                        msg = msging.recv().split()
                        type = msg[0]
                        if type == 'savepoint':
                            arg1 = msg[1]
                            arg2 = msg[2]
                            if arg2 == 'None':
                                psnapshot = None
                            else:
                                psnapshot = int(arg2)
                            ic = int(arg1)
                            sp = SavepointConnection(msging, max_id, ic, psnapshot)
                            self.savepoint_connections.append(sp)
                            msging.send('ok {0}'.format(max_id))
                            max_id += 1
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
                            if fd == conn.msging.sock.fileno():
                                conn.respond()
                                break
                        else:
                            #log.info("Additionally got: %s" % got)
                            log.info('Unknown fd: %s' % fd)
                            os.unlink(SOCK_NAME)
                            sys.exit(0)
        else:
            pass
    
    def list_savepoints(self):
        """Tell the controller to list all snapshots."""
        self.debuggee.send('showlist')
        reply = self.debuggee.recv()
        if reply != 'ok':
            raise Exception()
    
    def quit(self):
        self.debuggee.send('end')
        
    def activatesp(self, id):
        self.debuggee.send('activate {0}'.format(id))
        self.debuggee.close()
        #sys.exit(0)
        
#mp = MainProcess()
# 
#log.info("line1")
#log.info("Create Savepoint")
#sp1 = Savepoint()
##log.info("Savepoint created")
#log.info("line2") 
#sp2 = Savepoint()
#log.info("line3")
#
#skip = input('>> Skip Sp Aktivation? ')
#if skip != 'True':
#    log.info('>> Activate Sp')
#    mp.activatesp(sp1.id)
#log.info('Skipped: "%s"'%skip)
##mp.list_savepoints()
# 
#log.info('last') 
# 
##log.info('Show list')
##mp.list_savepoints() 
#
#mp.quit()
#
#log.info('main quit')
#sys.exit(0)