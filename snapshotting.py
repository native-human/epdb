#!/usr/bin/env python

import socket
import os
import sys
import select
import logging
import tempfile
import debug as log

import dbg
import shareddict

tmpfd, tmppath = tempfile.mkstemp(".dbg")

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
    # activated ... if the snaphot was activated or not
    def __init__(self, ic, psnapshot):
        self.ic = ic
        self.psnapshot = psnapshot
        # This is done before forking because of synchronization
        self.cpids = []
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCK_NAME)
        msging = Messaging(s)
        msging.send('snapshot {0} {1}'.format(self.ic, psnapshot))
        msg = msging.recv()
        args = msg.split(' ')
        cmd = args[0]
        self.id = int(args[1])
        if cmd != 'ok':
            # TODO better Error handling
            raise Exception()
        
        pid = os.fork()
        self.pid = pid
        if pid:
            # Parent
            self.activated = True 
            self.cpids.append(pid)
            while True:
                msg = msging.recv()
                args = msg.split()
                cmd = args[0]
                if cmd == "close":
                    #log.debug('Savepoint quit ... Wait for subprocess')
                    while self.cpids != []:
                        (pid,status) = os.wait()
                        idx = self.cpids.index(pid)
                        del self.cpids[idx]
                    #log.debug('Savepoint quit')
                    raise SnapshotExit()
                if cmd == "run":
                    steps = int(args[1])
                    rpid = os.fork()
                    if rpid:
                        self.cpids.append(rpid)
                    else:    
                        self.step_forward = steps
                        dbg.current_timeline = dbg.timelines.get_current_timeline()
                        dbg.sde = dbg.current_timeline.get_sde()
                        break
        else:
            dbg.current_timeline = dbg.timelines.get_current_timeline()
            dbg.sde = dbg.current_timeline.get_sde()
            self.step_forward = -1
            self.activated = False
        
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
        log.debug('cmd')
    
    def activate(self, steps=-1):
        self.msging.send('run {0}'.format(steps))
    
    def quit(self):
        self.msging.send('close')
        
class MainProcess:
    """This class forks the controller process. The controller process ends up
    in a loop. The other process returns with a connection to the controller"""
    def __init__(self):
        debuggee_sock, controller_sock = socket.socketpair()
        debuggee = Messaging(debuggee_sock)
        self.debuggee = debuggee
        controller = Messaging(controller_sock)
        backupcontroller = controller # TODO remove
        sp_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sp_sock.bind(SOCK_NAME)
        sp_sock.listen(10)
        self.savepoint_connections = []
        self.do_quit = False
        sdpid = shareddict.server(dofork=True)
        
        pid = os.fork()
        if pid:
            max_id = 0
            p = select.poll()
            p.register(controller.sock, select.POLLIN|select.POLLPRI)
            p.register(sp_sock, select.POLLIN|select.POLLPRI)
            while True:
                list = p.poll(100)
                if list == []:
                    if self.do_quit:
                        shareddict.shutdown()
                        os.waitpid(pid,0)
                        os.unlink(SOCK_NAME)
                        sys.exit(0)
                for event in list:
                    fd, ev = event
                    
                    # Controller Code
                    
                    if fd == controller.sock.fileno():
                        line = controller.recv()
                        words = line.rstrip().split(" ")
                        cmd = str(words[0])
                        if cmd == "end":
                            for conn in self.savepoint_connections:
                                try:
                                    conn.quit()
                                except:
                                    log.debug("Warning: Shuting down of Savepoint failed")
                            self.do_quit = True
                        elif cmd == 'connect':
                            arg = words[1]
                            controller.send("Connected " + arg)
                        elif cmd == 'showlist':
                            log.debug('ID           InstructionNr    PSnapshot')
                            log.debug('----------------------------')
                            for s in self.savepoint_connections:
                                log.debug("{0}    {1}     {2}".format(s.id, s.ic, s.psnapshot))
                            log.debug('Number of snapshots: %d' %
                                     len(self.savepoint_connections))
                            controller.send('ok')
                        elif cmd == 'activate': # TODO rename sp (savepoint) to snapshot
                            spid = int(words[1])
                            steps = int(words[2])
                            for s in self.savepoint_connections: # TODO rename savepoint connection
                                if s.id == spid:
                                    sp = s
                                    break
                            sp = self.savepoint_connections[spid]
                            sp.activate(steps)
                        else:
                            log.debug(cmd)
                            
                    # New Savepoint/Debuggee Connection
                    elif fd == sp_sock.fileno():
                        conn, addr = sp_sock.accept()
                        msging = Messaging(conn)
                        msg = msging.recv().split()
                        type = msg[0]
                        if type == 'snapshot':
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
                            if self.do_quit:
                                sp.quit()
                        else:
                            log.info("Critical Error")
                    else:
                        for conn in self.savepoint_connections:
                            if fd == conn.msging.sock.fileno():
                                conn.respond()
                                break
                        else:
                            log.info('Unknown fd: %s' % fd)
                            os.unlink(SOCK_NAME)
                            sys.exit(0)
        else:
            dbg.timelines = shareddict.TimelinesProxy()
            dbg.current_timeline = dbg.timelines.new_timeline()
            name = dbg.current_timeline.get_name() 
            dbg.timelines.set_current_timeline(name)
            dbg.sde = dbg.current_timeline.get_sde()
    
    def list_snapshots(self):
        """Tell the controller to list all snapshots."""
        #log.debug("Send List Savepoints")
        self.debuggee.send('showlist')
        reply = self.debuggee.recv()
        #log.debug('reply received')
        if reply != 'ok':
            raise Exception()
    
    def quit(self):
        try:
            self.debuggee.send('end')
        except:
            log.debug("Warning shutting down of snapshot server failed")
        
    def activatesp(self, id, steps=-1): # TODO rename to snapshot
        #log.info('activate {0} {1}'.format(id,steps))
        # TODO send own process id to the parent to wait for it, before start continuing
        self.debuggee.send('activate {0} {1}'.format(id,steps))
        self.debuggee.close()
        #sys.exit(0)
        
#tmp = MainProcess()
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