#!/usr/bin/env python

import socket
import os
import sys
import select
import logging
import tempfile
from epdblib import debug as log

from epdblib import dbg
from epdblib import shareddict

tmpfd, tmppath = tempfile.mkstemp(".dbg")

SOCK_DIR = tempfile.mkdtemp(prefix="epdb-")
SOCK_NAME = os.path.join(SOCK_DIR, 'snapshotting.sock')
#SOCK_NAME = tmppath

class SnapshotExit(Exception):
    """Raised when the controller process exits"""
    pass

class ControllerExit(Exception):
    """Raised when the controller process exits"""
    pass


class Snapshot:
    # activated ... if the snaphot was activated or not
    def __init__(self, ic, sock_name):
        self.ic = ic
        #self.psnapshot = psnapshot
        # This is done before forking because of synchronization
        self.cpids = []
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_name)
        self.msging = Messaging(s)
        self.msging.send('snapshot {0}'.format(self.ic))
        msg = self.msging.recv()
        args = msg.split(' ')
        cmd = args[0]
        self.id = int(args[1])
        if cmd != 'ok':
            # TODO better Error handling
            raise Exception()
            
        oldpid = os.getpid()
        pid = os.fork()
        self.pid = pid
        if pid:
            # Parent
            dbg.cpids.append(pid)
            dbg.current_timeline = dbg.timelines.get_current_timeline()
            dbg.nde = dbg.current_timeline.get_nde()
            self.step_forward = -1
            self.activated = False
            self.activation_type = None
        else:
            del dbg.cpids[:]
            self.block()

    def block(self):
        self.activated = True
        while True:
            msg = self.msging.recv()
            args = msg.split()
            cmd = args[0]
            if cmd == "close":
                while dbg.cpids != []:
                    (pid,status) = os.wait()
                    idx = dbg.cpids.index(pid)
                    del dbg.cpids[idx]
                raise SnapshotExit()
            if cmd == "run":
                steps = int(args[1])
                rpid = os.fork()
                if rpid:
                    dbg.cpids.append(rpid)
                else:
                    del dbg.cpids[:]
                    self.activation_type = "step_forward"
                    self.step_forward = steps
                    dbg.current_timeline = dbg.timelines.get_current_timeline()
                    dbg.nde = dbg.current_timeline.get_nde()
                    #dbg.undod = dbg.current_timeline.get_ude()
                    break

            if cmd == "runic":
                ic = int(args[1])
                rpid = os.fork()
                if rpid:
                    dbg.cpids.append(rpid)
                else:
                    del dbg.cpids[:]
                    self.activation_type = "stop_at_ic"
                    self.stop_at_ic = ic
                    dbg.current_timeline = dbg.timelines.get_current_timeline()
                    dbg.nde = dbg.current_timeline.get_nde()
                    #dbg.undod = dbg.current_timeline.get_ude()
                    break

            elif cmd == "runnext":
                # Run until a given nocalls is reached
                nocalls = int(args[1])
                rpid = os.fork()
                if rpid:
                    dbg.cpids.append(rpid)
                else:
                    del dbg.cpids[:]
                    #self.step_forward = steps
                    self.activation_type = "stopatnocalls"
                    self.nocalls = nocalls
                    dbg.current_timeline = dbg.timelines.get_current_timeline()
                    dbg.nde = dbg.current_timeline.get_nde()
                    #dbg.undod = dbg.current_timeline.get_ude()
                    break
            elif cmd == "runcontinue":
                # Run until a given nocalls is reached
                rpid = os.fork()
                if rpid:
                    dbg.cpids.append(rpid)
                else:
                    del dbg.cpids[:]
                    #self.step_forward = steps
                    self.activation_type = "continue"
                    dbg.current_timeline = dbg.timelines.get_current_timeline()
                    dbg.nde = dbg.current_timeline.get_nde()
                    #dbg.undod = dbg.current_timeline.get_ude()
                    break
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
        msg = msg.decode('ascii')
        return msg.rstrip()
    def close(self):
        self.sock.close()

class SnapshotConnection:
    def __init__(self, msging, id, ic):
        self.msging = msging
        self.id = id
        self.ic = ic

    def respond(self):
        cmd = self.msging.recv()
        log.debug('cmd')

    def activate(self, steps=-1):
        self.msging.send('run {0}'.format(steps))

    def activateic(self, ic):
        self.msging.send('runic {0}'.format(ic))

    def activatenext(self, nocalls):
        self.msging.send('runnext {0}'.format(nocalls))

    def activatecontinue(self):
        self.msging.send('runcontinue')

    def quit(self):
        self.msging.send('close')

class MainProcess:
    """This class forks the controller process. The controller process ends up
    in a loop. The other process returns with a connection to the controller"""
    def __init__(self, startserver=True):
        debuggee_sock, controller_sock = socket.socketpair()
        debuggee = Messaging(debuggee_sock)
        self.debuggee = debuggee
        self.controller = Messaging(controller_sock)
        self.sp_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock_name = SOCK_NAME
        self.sp_sock.bind(self.sock_name)
        self.sp_sock.listen(10)
        self.snapshot_connections = []
        self.do_quit = False
        
        if startserver:
            self.start_shareddict_server()
            self.pid = os.fork()
            if self.pid:
                self.server()
                os.waitpid(self.pid,0) # wait for the child process
                shareddict.shutdown(dbg.shareddict_sock)
                sys.exit(0)
            else:
                self.set_up_client()

    def start_shareddict_server(self):
        sockfile = os.path.join(SOCK_DIR, 'shareddict.sock')
        dbg.shareddict_sock = sockfile
        sdpid = shareddict.server(sockfile, dofork=True)

    def set_up_client(self):
        dbg.timelines = shareddict.TimelinesProxy("timelines", dbg.shareddict_sock)
        dbg.current_timeline = dbg.timelines.new_timeline()
        name = dbg.current_timeline.get_name()
        dbg.timelines.set_current_timeline(name)
        dbg.nde = dbg.current_timeline.get_nde()
            
    def server(self):
        max_id = 0
        p = select.poll()
        p.register(self.controller.sock, select.POLLIN|select.POLLPRI)
        p.register(self.sp_sock, select.POLLIN|select.POLLPRI)
        while True:
            list = p.poll(100)
            if list == []:
                if self.do_quit:
                    os.unlink(self.sock_name)
                    return
                    #sys.exit(0)
            for event in list:
                fd, ev = event

                # Controller Code

                if fd == self.controller.sock.fileno():
                    line = self.controller.recv()
                    words = line.rstrip().split(" ")
                    cmd = str(words[0])
                    if cmd == "end":
                        for conn in self.snapshot_connections:
                            try:
                                conn.quit()
                            except:
                                log.debug("Warning: Shuting down of Savepoint failed")
                        self.do_quit = True
                    elif cmd == 'connect':
                        arg = words[1]
                        self.controller.send("Connected " + arg)
                    elif cmd == 'showlist':
                        log.debug('ID           InstructionNr    PSnapshot')
                        log.debug('----------------------------')
                        for s in self.snapshot_connections:
                            log.debug("{0}    {1}".format(s.id, s.ic))
                        log.debug('Number of snapshots: %d' %
                                 len(self.snapshot_connections))
                        self.controller.send('ok')
                    elif cmd == 'activate': # TODO rename sp (savepoint) to snapshot
                        spid = int(words[1])
                        steps = int(words[2])
                        for s in self.snapshot_connections: # TODO rename savepoint connection
                            if s.id == spid:
                                sp = s
                                break
                        sp = self.snapshot_connections[spid]
                        sp.activate(steps)

                    elif cmd == 'activateic':
                        ssid = int(words[1])
                        ic = int(words[2])
                        for s in self.snapshot_connections: # TODO rename savepoint connection
                            if s.id == ssid:
                                sp = s
                                break
                        sp = self.snapshot_connections[ssid]
                        sp.activateic(ic)

                    elif cmd == 'activatenext':
                        ssid = int(words[1])
                        nocalls = int(words[2])
                        for s in self.snapshot_connections: # TODO rename savepoint connection
                            if s.id == ssid:
                                ss = s
                                break
                        ss = self.snapshot_connections[ssid]
                        ss.activatenext(nocalls)

                    elif cmd == 'activatecontinue':
                        ssid = int(words[1])
                        for s in self.snapshot_connections: # TODO rename savepoint connection
                            if s.id == ssid:
                                ss = s
                                break
                        ss = self.snapshot_connections[ssid]
                        ss.activatecontinue()
                    else:
                        log.debug(cmd)

                # New Savepoint/Debuggee Connection
                elif fd == self.sp_sock.fileno():
                    conn, addr = self.sp_sock.accept()
                    msging = Messaging(conn)
                    msg = msging.recv().split()
                    type = msg[0]
                    if type == 'snapshot':
                        arg1 = msg[1]
                        ic = int(arg1)
                        sp = SnapshotConnection(msging, max_id, ic)
                        self.snapshot_connections.append(sp)
                        msging.send('ok {0}'.format(max_id))
                        max_id += 1
                        if self.do_quit:
                            sp.quit()
                    else:
                        log.info("Critical Error")
                else:
                    for conn in self.snapshot_connections:
                        if fd == conn.msging.sock.fileno():
                            conn.respond()
                            break
                    else:
                        log.info('Unknown fd: %s' % fd)
                        os.unlink(self.sock_name)
                        #sys.exit(0)
                        return

    def make_snapshot(self, ic):
        return Snapshot(ic, self.sock_name)

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

    def activateic(self, id, ic):
        self.debuggee.send('activateic {0} {1}'.format(id,ic))
        self.debuggee.close()

    def activatenext(self, id, nocalls):
        self.debuggee.send('activatenext {0} {1}'.format(id,nocalls))
        self.debuggee.close()

    def activatecontinue(self, id):
        self.debuggee.send('activatecontinue {0}'.format(id))
        self.debuggee.close()