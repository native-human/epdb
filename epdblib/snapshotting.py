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

import shutil
import time

class SnapshotExit(Exception):
    """Raised when the controller process exits"""
    pass

class ControllerExit(Exception):
    """Raised when the controller process exits"""
    pass

class Snapshot:
    # activated ... if the snaphot was activated or not
    def __init__(self, ic, sockaddr):
        self.ic = ic
        #self.psnapshot = psnapshot
        # This is done before forking because of synchronization
        self.cpids = []
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sockaddr)
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
                mainpid = int(args[1])
                
                if mainpid in dbg.cpids: # The main pid will be closed after
                                        # after the quit confirmation
                    dbg.cpids.remove(mainpid)
                    mainpids = [mainpid]
                else:
                    mainpids = []
                while dbg.cpids != []:
                    (pid,status) = os.wait()
                    idx = dbg.cpids.index(pid)
                    del dbg.cpids[idx]
                self.msging.send('quitdone')
                while mainpids != []:
                    mainpid = mainpids.pop()
                    (pid,status) = os.wait()
                time.sleep(0.5) # TODO some better synchronization needed
                raise SnapshotExit()
            if cmd == "run":
                steps = int(args[1])
                rpid = os.fork()
                if rpid:
                    dbg.cpids.append(rpid)
                else:
                    log.debug("")
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
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.recv_msg = b''

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
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
        msg = msg.decode('ascii')
        return msg.rstrip()

    def recv_async(self):
        msg = b''
        while len(msg) < self.MSG_LEN:
            try:
                chunk = self.sock.recv(self.MSG_LEN-len(msg), socket.MSG_DONTWAIT)
            except socket.error:
                return None
            if chunk == b'':
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
        
        self.quitted = False

    def fileno(self):
        return self.msging.sock.fileno()

    def respond(self):
        cmd = self.msging.recv()

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
        done = self.msging.recv()
        if done != 'done':
            log.debug("Error")
            
    def send_quit(self, mainpid):
        self.msging.send('close ' + str(mainpid))
       # self.quitted = False
    
    def recv_quitdone(self):
        #try:
        msg = self.msging.recv()
        #except:
        #    log.debug("Broken connection. Assume Quit")
        #    self.quitted = True
        if msg == 'quitdone':
            self.quitted = True
        else:
            log.debug("Error received: " + repr(msg) + "instead of quitdone")
    
    #def quitted(self):
    #    if self.quitted:
    #        return True
    #    done = self.msging.recv()
    #    log.debug("close done")
    #    if done != 'done':
    #        log.debug("Error")

class MainProcess:
    """This class forks the controller process. The controller process ends up
    in a loop. The other process returns with a connection to the controller"""
    def __init__(self, proxycreator=None, tempdir=None, sockname='snapshotting.sock',
                 startserver=True, resources=[], resource_paths=[]):
        if tempdir is None:
            dir = tempfile.mkdtemp(prefix="epdb-snap")
        else:
            dir = tempdir
        self.shareddict_created = False
        self.tempdir = tempdir
        self.dir = dir
        self.sockaddr = os.path.join(dir, sockname)
        self.proxycreator = proxycreator
        
        debuggee_sock, controller_sock = socket.socketpair()
        debuggee = Messaging(debuggee_sock)
        self.debuggee = debuggee
        self.controller = Messaging(controller_sock) # TODO rename sp_sock
        self.sp_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sp_sock.bind(self.sockaddr)
        self.sp_sock.listen(10)
        self.snapshot_connections = []
        self.do_quit = False
        self.snapshot_class = Snapshot
        
        if startserver:
            if not self.proxycreator:
                self.start_shareddict_server(resources=resources, resource_paths=resource_paths)
                self.shareddict_created = True
                self.proxycreator = shareddict.ProxyCreator(self.dir)
            self.pid = os.fork()
            if self.pid:
                shareddict.initialize_resources(resources, resource_paths)
                self.server()
                os.waitpid(self.pid,0) # wait for the child process
                sys.exit(0)
            else:
                self.set_up_client()

    def start_shareddict_server(self, resources=[], resource_paths=[]):
        #sockfile = os.path.join(SOCK_DIR, 'shareddict.sock')
        #dbg.shareddict_sock = sockfile
        sdpid = shareddict.server(self.dir, dofork=True, resources=resources,
                                  resource_paths=resource_paths)

    def set_up_client(self):
        from epdblib import dbg
        #dbg.timelines = shareddict.TimelinesProxy("timelines", dbg.shareddict_sock)
        dbg.timelines = self.proxycreator.create_timelines("timelines")
        dbg.current_timeline = dbg.timelines.new_timeline()
        name = dbg.current_timeline.get_name()
        dbg.timelines.set_current_timeline(name)
        dbg.nde = dbg.current_timeline.get_nde()
            
    def server(self):
        max_id = 0
        p = select.poll()
        p.register(self.controller.sock, select.POLLIN|select.POLLPRI)
        p.register(self.sp_sock, select.POLLIN|select.POLLPRI)
        quitrecvinitiated = False
        while True:
            list = p.poll(200)
            if list == []:
                if self.do_quit:
                    #log.debug("not quitted " + str(notquitted))
                    if not quitrecvinitiated:
                        for sc in self.snapshot_connections:
                            p.register(sc.fileno(), select.POLLIN|select.POLLPRI)
                        quitrecvinitiated = True
                    notquitted = [s.quitted for s in self.snapshot_connections if s.quitted == False]
                    if notquitted == []:
                        self.controller.send("done")
                        self.clear_tmp_file()
                        return
                        #sys.exit(0)
            for fd, ev in list:
                # Controller Code
                if fd == self.controller.sock.fileno():
                    line = self.controller.recv()
                    words = line.rstrip().split(" ")
                    cmd = str(words[0])
                    if cmd == "end":
                        mainpid = int(words[1])
                        notquitted = [s.quitted for s in self.snapshot_connections if s.quitted == False]
                        for i,conn in enumerate(self.snapshot_connections):
                            try:
                                conn.send_quit(mainpid)
                            except:
                                import traceback
                                exctype,exc,tb = sys.exc_info()
                                print(exctype, exc)
                                #print("Exception:", exc.message)
                                traceback.print_tb(tb)
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
                    elif cmd == 'activate':
                        ssid = int(words[1])
                        steps = int(words[2])
                        for s in self.snapshot_connections:
                            if s.id == ssid:
                                ss = s
                                break
                        ss = self.snapshot_connections[ssid]
                        ss.activate(steps)

                    elif cmd == 'activateic':
                        ssid = int(words[1])
                        ic = int(words[2])
                        for s in self.snapshot_connections:
                            if s.id == ssid:
                                ss = s
                                break
                        ss = self.snapshot_connections[ssid]
                        ss.activateic(ic)

                    elif cmd == 'activatenext':
                        ssid = int(words[1])
                        nocalls = int(words[2])
                        for s in self.snapshot_connections:
                            if s.id == ssid:
                                ss = s
                                break
                        ss = self.snapshot_connections[ssid]
                        ss.activatenext(nocalls)

                    elif cmd == 'activatecontinue':
                        ssid = int(words[1])
                        for s in self.snapshot_connections:
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
                        ss = SnapshotConnection(msging, max_id, ic)
                        self.snapshot_connections.append(ss)
                        msging.send('ok {0}'.format(max_id))
                        max_id += 1
                        if self.do_quit:
                            ss.send_quit()
                    else:
                        log.info("Critical Error")
                
                # Message from snapshot
                elif fd in [s.fileno() for s in self.snapshot_connections]:
                    ss_conn = [s for s in self.snapshot_connections if fd == s.fileno()][0]
                    ss_conn.recv_quitdone()
                else:
                    for conn in self.snapshot_connections:
                        if fd == conn.msging.sock.fileno():
                            conn.respond()
                            break
                    else:
                        log.info('Unknown fd: %s' % fd)
                        self.clear_tmp_file()
                        #sys.exit(0)
                        return

    def clear_tmp_file(self):
        """Clear temporary file if the MainProcess has created it, otherwise
        let the callee delete it."""
        if self.tempdir is None:
            shutil.rmtree(self.dir)    

    def make_snapshot(self, ic):
        #print(Snapshot, self)
        return Snapshot(ic, self.sockaddr)
        #return self.snapshot_class(ic, self.sockaddr)
        
    def list_snapshots(self):
        """Tell the controller to list all snapshots."""
        self.debuggee.send('showlist')
        reply = self.debuggee.recv()
        #log.debug('reply received')
        if reply != 'ok':
            raise Exception()

    def quit(self):
        try:
            self.debuggee.send('end '+str(os.getpid()))
            done = self.debuggee.recv()
            if done != 'done':
                log.debug("Something went wrong during shutdown")
        except:
            log.debug("Warning shutting down of snapshot server failed")
        if self.shareddict_created:
            shareddict.shutdown(self.dir)

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