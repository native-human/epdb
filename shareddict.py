#!/usr/bin/env python

import multiprocessing.connection
import socket
import os
import time
import struct
import pickle
import sys
import collections
import select
from debug import debug
    
def connect(address):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(address)
    return Connection(sock, address=address)
    
class Connection:
    def __init__(self, sock, address=None):
        self.sock = sock
        self.address = address
    def send(self, b):
        assert isinstance(b, bytes)
        l = struct.pack('!Q', len(b))
        self.sock.send(l)
        self.sock.send(b)
    def recv(self):
        l = self.sock.recv(8, socket.MSG_WAITALL)
        if l == b'':
            return b''
        l = struct.unpack('!Q', l)[0]
        ret = self.sock.recv(l, socket.MSG_WAITALL)
        return ret
    def close(self):
        self.sock.close()
        
    
def listen(address):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(address)
    sock.listen(5)
    return Listener(sock)
    
class Listener:
    def __init__(self, sock):
        self.sock = sock
    def accept(self):
        client,address = self.sock.accept()
        return Connection(client, address=address)

class ServerDict(dict):
    def __iter__(self):
        return dict.copy(self)
    def keys(self):
        return list(dict.keys(self))
    def _copy(self): # The normal copy version returns a dict
        r = ServerDict()
        r.update(self)
        return r

class ServerList(list):
    def __iter__(self):
        return self[:]
        
class ServerTimeline:
    def __init__(self, timelines, name="head", snapshots=[], sde=None, ic=0):
        self.snapshots = snapshots
        self.timelines = timelines
        self.name = name
        self.firstic = 0
        self.lastic = 0
        self.ic = 0
        if name in timelines.sde_dict.keys():
            raise Exception("Name already exist in sde")
        if sde:
            timelines.sde_dict[name] = sde
        else:
            timelines.sde_dict[name] = ServerDict()
    
    def _add_by_id(self, snapshotid):
        try:
            self.timelines.snapshotdict[snapshotid].references += 1
            self.snapshots.append(snapshotid)
        except:
            raise Exception("Snapshot doesn't exist " + str(snaphotid))
        
    def add(self, snapshot):
        """Adds a new snapshot to the timeline"""
        if hasattr(snapshot, 'id'):
            self._add_by_id(snapshot.id)
        else:
            if type(snapshot) == int or type(snapshot) == long:
                self._add_by_id(snapshot)
            else:
                raise Exception("Couldn't add snapshot")
    
    def show(self):
        debug("Showing Timeline:", self.name)
        for e in self.snapshots:
            debug(e)
        debug('')
    
    def copy(self, name, ic):
        """Creates a copy of the timeline. name is the new name of the timeline
        ic the instruction count. ic is used to set the sde dictionary correctly"""
        oldsde = self.timelines.sde_dict[self.name].copy()
        sde = {k:oldsde[k] for k in oldsde if k < ic}
        copy = ServerTimeline(self.timelines, name, self.snapshots, sde=sde)
        for k in self.snapshots:
            self.timelines.snapshotdict[k].references += 1
        self.timelines.add(copy)
        return "timeline." + name
    
    def get_sde(self):
        return "sde." + self.name
    
    def get_name(self):
        return self.name
    
    def deactivate(self, ic):
        """Deactivate timeline, saves the instruction count"""
        self.ic = ic
        
    def get_ic(self):
        return self.ic

class ServerTimelines:
    def __init__(self, snapshotdict, sde_dict):
        self.snapshotdict = snapshotdict
        self.sde_dict = sde_dict
        self.timelines = {} # name:timeline
        self.current_timeline = None
    
    def _get(self, name):
        """Returns a Server Timeline"""
        return self.timelines[name]
    
    def get(self, name):
        """Returns objref to the server timeline"""
        if name in self.timelines.keys():
            return "timeline."+name
        
    def get_current_timeline(self):
        """Returns the current timeline"""
        return "timeline." + self.current_timeline
        
    def set_current_timeline(self, name):
        """Sets the current timeline"""
        if not name in self.timelines:
            raise Exception("Timeline does not exist")
        self.current_timeline = name
        
    def new_timeline(self, name="head", snapshotdict={}):
        """Creates a new timeline and returns a objref"""
        if name in self.timelines.keys():
            raise Exception("Timeline with this name already exist")
        new = ServerTimeline(self, name)
        self.timelines[new.name] = new
        r = "timeline." + new.name
        return r
    
    def add(self, timeline):
        """Adds a new timeline to the dict. Doesn't change the references on the snapshots"""
        if timeline.name in self.timelines:
            raise Exception("Timeline already exist")
        self.timelines[timeline.name] = timeline
    
    def show(self):
        debug("Show values")
        for k in self.timelines.keys():
            debug(self.timelines[k].name)
            
def server(dofork=False):
    sde = ServerDict()
    bplist = ServerDict()   # weird naming, but conforming to bdb
    bpbynumber = ServerList()
    bpbynumber.append(None)
    breaks = ServerDict()
    snapshots = ServerDict()
    sde_dict = {}
    timelines = ServerTimelines(snapshots, sde_dict)
    #current_timeline = ServerTimeline(snapshots, timelines)
    
    try:
        os.unlink('/tmp/shareddict')
    except OSError:
        pass
    server = listen('/tmp/shareddict')
    if dofork:
        sdpid = os.fork()
        if not sdpid:
            return sdpid
    do_quit = False
    connectiondict = {}
    poll = select.epoll()
    poll.register(server.sock, select.EPOLLIN|select.EPOLLPRI|select.EPOLLHUP)
    while not do_quit:
        list = poll.poll(100)
        for fileno, event in list:
            if fileno == server.sock.fileno():
                newconnection = server.accept()
                connectiondict[newconnection.sock.fileno()] = newconnection
                poll.register(newconnection.sock, select.EPOLLIN|select.EPOLLPRI|select.EPOLLHUP)
            else:
                try:
                    if event | select.EPOLLIN:
                        conn = connectiondict[fileno]
                        bstream = conn.recv()
                        try:
                            objref,method,args,kargs = pickle.loads(bstream)
                            if objref == 'sde':
                                r = getattr(sde, method)(*args, **kargs)
                            elif objref == 'bplist':
                                r = getattr(bplist, method)(*args, **kargs)
                            elif objref == 'bpbynumber':
                                r = getattr(bpbynumber, method)(*args, **kargs)
                            elif objref == 'breaks':
                                r = getattr(breaks, method)(*args, **kargs)
                            elif objref == 'snapshots':
                                r = getattr(snapshots, method)(*args, **kargs)
                            elif objref == 'timelines':
                                r = getattr(timelines, method)(*args, **kargs)
                            elif objref.startswith('timeline.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(timelines._get(id), method)(*args, **kargs)
                            elif objref.startswith('sde.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(sde_dict[id], method)(*args, **kargs)
                            elif objref == 'control':
                                r = None
                                if method == 'shutdown':
                                    do_quit = True
                        except Exception as e:
                            conn.send(pickle.dumps(('EXC', e)))
                        else:
                            conn.send(pickle.dumps(('RET', r)))
                    if event | select.EPOLLHUP:
                        pass
                    elif event == select.EPOLLPRI:
                        pass
                    else:
                        debug('Server: Unknown event')
                except socket.error:
                    poll.unregister(fileno)
    if dofork:
        sys.exit(0)
        
def client():
    con = connect('/tmp/shareddict')
    
    txt = input()
    while txt != 'exit':
        s = txt.split()
        s += [''] * (3-len(s))
        command, idx, value = s
        if command == 'set':
            con.send(pickle.dumps(('__setitem__', (idx, value), {})))
            t,r = pickle.loads(con.recv())
                
        elif command == 'get':
            con.send(pickle.dumps(('__getitem__', (idx), {})))
            t,r = pickle.loads(con.recv())
        if t == 'RET':
            debug(r)
        elif t == 'EXC':
            raise r
        else:
            debug('Unknown return value')
        txt = input()
    con.close()
    
class DictProxy:
    def __init__(self, objref, conn=None):
        if conn:
            self.conn = conn
        else:
            self.conn = connect('/tmp/shareddict')
        self.objref = objref
    
    def _remote_invoke(self, method, args, kargs):
        self.conn.send(pickle.dumps((self.objref, method, args, kargs)))
        t,r = pickle.loads(self.conn.recv())
        if t == 'RET':
            return r
        elif t == 'EXC':
            raise r
        else:
            debug('Unknown return value')
            
    def __getitem__(self, idx):
        return self._remote_invoke('__getitem__', (idx,), {})
        
    def __setitem__(self, idx, value):
        return self._remote_invoke('__setitem__', (idx, value), {})
        
    def __iter__(self): 
        return self._remote_invoke('__iter__',(), {}).__iter__()

    def __contains__(self, k):
        return self._remote_invoke('__contains__',(k,), {})
        
    def __str__(self):
        return "DictProxy: " + self._remote_invoke('__str__',(), {})
        
    def __repr__(self):
        return "DictProxy: " + self._remote_invoke('__repr__',(), {})
        
    def copy(self):
        return self._remote_invoke('copy',(), {})
        
    def __delitem__(self, k):
        return self._remote_invoke('__delitem__',(k,), {})
        
    def update(self, d):
        return self._remote_invoke('update',(d,), {})

    def keys(self): # TODO this doesn't work
        return self._remote_invoke('keys',(), {})
        
    def values(self): # TODO this doesn't work
        return self._remote_invoke('values',(), {})
        
    def __len__(self):
        return self._remote_invoke('__len__',(), {})
    
    def clear(self):
        return self._remote_invoke('clear',(), {})

class ListProxy:
    def __init__(self, objref, conn=None):
        if conn:
            self.conn = conn
        else:
            self.conn = connect('/tmp/shareddict')
        self.objref = objref
    
    def _remote_invoke(self, method, args, kargs):
        self.conn.send(pickle.dumps((self.objref, method, args, kargs)))
        t,r = pickle.loads(self.conn.recv())
        if t == 'RET':
            return r
        elif t == 'EXC':
            raise r
        else:
            debug('Unknown return value')
            
    def __getitem__(self, idx):
        return self._remote_invoke('__getitem__', (idx,), {})
        
    def __setitem__(self, idx, value):
        return self._remote_invoke('__setitem__', (idx, value), {})
        
    def __iter__(self): 
        return self._remote_invoke('__iter__',(), {}).__iter__()

    def __contains__(self, k):
        return self._remote_invoke('__contains__',(k,), {})
        
    def __str__(self):
        return "ListProxy: " + self._remote_invoke('__str__',(), {})
        
    def __repr__(self):
        return "ListProxy: " + self._remote_invoke('__repr__',(), {})

    def __sizeof__(self):
        return self._remote_invoke('__sizeof__',(), {})

    def append(self, object):
        return self._remote_invoke('append',(object,), {})


    def count(self, value):
        return self._remote_invoke('count',(value,), {})
 
    def extend(self, iterable):
        return self._remote_invoke('extend',(iterable,), {})
 
    def index(self, value, *args):
        return self._remote_invoke('index',(iterable,)+args, {})
 
    def insert(self, index, object):
        return self._remote_invoke('insert',(index, object), {})
 
    def pop(self, *args):
        return self._remote_invoke('pop',args, {})
 
    def remove(self, value):
        return self._remote_invoke('remove',(value,), {})
 
    def reverse(self):
        return self._remote_invoke('reverse',(), {})
    
    def sort(self, key=None, reverse=False):
        return self._remote_invoke('sort',(key, reverse), {})

class TimelineProxy:
    def __init__(self, objref, conn=None):
        if conn:
            self.conn = conn
        else:
            self.conn = connect('/tmp/shareddict')
        self.objref = objref
    
    def _remote_invoke(self, method, args, kargs):
        self.conn.send(pickle.dumps((self.objref, method, args, kargs)))
        t,r = pickle.loads(self.conn.recv())
        if t == 'RET':
            return r
        elif t == 'EXC':
            raise r
        else:
            debug('Unknown return value')
            
    def add(self, snapshot):
        return self._remote_invoke('add',(snapshot,), {})
        
    def show(self):
        return self._remote_invoke('show',(), {})
        
    def copy(self, name, ic):
        objref = self._remote_invoke('copy',(name, ic), {})
        proxy = TimelineProxy(objref=objref, conn=self.conn)
        return proxy
    
    def get_name(self):
        return self._remote_invoke('get_name',(), {})
        
    def get_sde(self):
        objref = self._remote_invoke('get_sde',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy
    
    def deactivate(self, ic):
        return self._remote_invoke('deactivate',(ic,), {})
        
    def get_ic(self):
        return self._remote_invoke('get_ic',(), {})
        

class TimelinesProxy:
    def __init__(self, objref="timelines", conn=None):
        if conn:
            self.conn = conn
        else:
            self.conn = connect('/tmp/shareddict')
        self.objref = objref
    
    def _remote_invoke(self, method, args, kargs):
        self.conn.send(pickle.dumps((self.objref, method, args, kargs)))
        t,r = pickle.loads(self.conn.recv())
        if t == 'RET':
            return r
        elif t == 'EXC':
            raise r
        else:
            debug('Unknown return value')
    
    def get(self, name):
        objref = self._remote_invoke('get',(name,), {})
        proxy = TimelineProxy(objref=objref, conn=self.conn)
        return proxy
    
    def new_timeline(self, name="head", snapshotdict={}):
        objref = self._remote_invoke('new_timeline',(name,snapshotdict), {})
        proxy = TimelineProxy(objref=objref, conn=self.conn)
        return proxy
    
    def get_current_timeline(self):
        objref = self._remote_invoke('get_current_timeline',(), {})
        proxy = TimelineProxy(objref=objref, conn=self.conn)
        return proxy
    
    def set_current_timeline(self, name):
        return self._remote_invoke('set_current_timeline',(name,), {})
    
    def show(self):
        return self._remote_invoke('show',(), {})
            
def shutdown():
    debug("Shutting down")
    conn = connect('/tmp/shareddict')
    conn.send(pickle.dumps(('control', 'shutdown', (), {})))
    

if __name__ == '__main__':
    server(dofork=True)
    tls = TimelinesProxy()
    tl = tls.new_timeline()
    tls.show()
    tl.show()
    shutdown()