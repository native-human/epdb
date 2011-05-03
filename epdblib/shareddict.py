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
import base64
import re
import traceback
import _thread
import tempfile
from epdblib.debug import debug
from epdblib import dbg

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
    def close(self):
        self.sock.close()

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
    def __init__(self, timelines, name="main", snapshots=[], nde=None, ude=None,
                 ic=0,
                 next=None, cont=None, resources=None, managers=None,
                 stdout_cache = ""
                 #, rnext=None, rcontinue=None
                 ):
        self.stdout_cache = stdout_cache
        self.snapshots = snapshots
        self.timelines = timelines
        self.name = name
        self.firstic = 0
        self.lastic = 0
        self.ic = ic
        self.max_ic = ic
        if name in timelines.nde_dict.keys():
            raise Exception("Name already exist in nde")
        if name in timelines.ude_dict.keys():
            raise Exception("Name already exist in ude")
        if nde:
            timelines.nde_dict[name] = nde
        else:
            timelines.nde_dict[name] = ServerDict()

        if ude:
            timelines.ude_dict[name] = ude
        else:
            timelines.ude_dict[name] = ServerDict()

        if next:
            timelines.next_dict[name] = next
        else:
            timelines.next_dict[name] = ServerDict()

        if cont:
            timelines.continue_dict[name] = cont
        else:
            timelines.continue_dict[name] = ServerDict()


        if resources:
            self.resources = resources
        else:
            self.resources = ServerDict()
        #debug("new resource set:", self.resources, type(self.resources))
        timelines.resources_dict[name] = self.resources

        if managers:
            self.managers = managers
        else:
            self.managers = ServerDict()
        timelines.managers_dict[name] = self.managers

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

    def copy(self, name, ic):
        """Creates a copy of the timeline. name is the new name of the timeline
        ic the instruction count. ic is used to set the nde dictionary correctly"""
        oldnde = self.timelines.nde_dict[self.name].copy()
        oldude = self.timelines.ude_dict[self.name].copy()
        nde = {k:oldnde[k] for k in oldnde if k < ic}
        ude = {k:oldude[k] for k in oldude if k < ic}
        # TODO copy resources and managers
        #debug("Copy resources and managers")
        oldresources = self.timelines.resources_dict[self.name].copy()
        oldmanagers = self.timelines.managers_dict[self.name].copy()
        managers = {}
        resources = ServerDict()
        for typ,location in oldresources:
            oldresource = oldresources[(typ,location)]
            #debug("copy oldresource", oldresource)
            resource = ServerDict()
            for i in oldresource.copy():
                if i <= ic:
                    resource[i] = oldresource[i]
            if resource != {}:
                resources[(typ,location)] = resource
                managers[(typ,location)] = oldmanagers[(typ,location)]
            #debug("resource:", resource)

        snapshots = []
        for sid in self.snapshots:
            sdata = self.timelines.snapshotdict[sid]
            sic = sdata.ic
            if sic <= ic:
                snapshots.append(sid)
        copy = ServerTimeline(self.timelines, name, snapshots, nde=nde,
                              ude=ude, resources=resources, managers=managers,
                              stdout_cache=self.stdout_cache)
        for k in snapshots:
            self.timelines.snapshotdict[k].references += 1
        self.timelines.add(copy)
        return "timeline." + name

    def get_nde(self):
        return "nde." + self.name

    def get_ude(self):
        return "ude." + self.name

    def get_rnext(self):
        return "rnext." + self.name

    def get_rcontinue(self):
        return "rcontinue." + self.name

    def get_next(self):
        return "next." + self.name

    def get_continue(self):
        return "continue." + self.name

    def get_name(self):
        return self.name

    def deactivate(self, ic):
        """Deactivate timeline, saves the instruction count"""
        self.ic = ic
        if ic > self.max_ic:
            self.max_ic = ic

    def get_ic(self):
        return self.ic

    def get_max_ic(self):
        #debug("Server get maxic: ", self.max_ic)
        return self.max_ic

    def set_max_ic(self, maxic):
        #debug("Server set maxic: ", maxic)
        self.max_ic = maxic

    def get_snapshots(self):
        return self.snapshots

    def get_resource(self, type, location):
        enclocation = str(base64.b64encode(bytes(location, 'utf-8')), 'utf-8')
        return "resources." + self.name + "." + type + "." + enclocation

    def get_resources(self):
        return "resources." + self.name

    #def new_server_resource(self, type, location, timeline):
    #    resource = ServerDict()
    #    enclocation = str(base64.b64encode(bytes(location, 'utf-8')),'utf-8')
    #    debug("new server resource:", timeline, type, enclocation)
    #    return resource

    def new_resource(self, type, location):
        """Creates a new resource if it does not exist"""
        #debug("NEW RESOURCE", type, location, self.name)
        if not (type, location) in self.resources:
            #debug("Create new resource: ", type, location)
            self.resources[(type, location)] = ServerDict()
        else:
            debug("Don't create new resource, because it already exists: ", type, location)
        #debug("NEW1")
        enclocation = str(base64.b64encode(bytes(location, 'utf-8')),'utf-8')
        #debug("NEW2")
        #debug("new resource:", self.name, type, enclocation)
        return "resources." + self.name + "." + type + "." + enclocation

    def create_manager(self, identification, manager):
        """identification is a tuple (type, location)"""
        self.managers[identification] = manager
        return self.managers[identification]

    def get_manager(self, identification):
        return self.managers[identification]
        #return "managers." + self.name + "." + type + "." + enclocation

    def update_manager(self, identification, manager):
        if identification in self.managers:
            self.managers[identification] = manager
        else:
            raise

    def update_stdout_cache(self, text):
        self.stdout_cache += text

    def get_stdout_cache(self):
        return self.stdout_cache

    def set_stdout_cache(self, text):
        self.stdout_cache = text


class ServerTimelines:
    def __init__(self, snapshotdict, nde_dict, ude_dict
                 #,rnext_dict, rcontinue_dict
                 ,next_dict, continue_dict,
                 resources_dict, managers_dict
                 ):
        self.snapshotdict = snapshotdict
        self.nde_dict = nde_dict
        self.ude_dict = ude_dict
        #self.rnext_dict = rnext_dict
        #self.rcontinue_dict = rcontinue_dict
        self.next_dict = next_dict
        self.continue_dict = continue_dict
        self.resources_dict = resources_dict
        self.managers_dict = managers_dict
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
        if not name is None and not name in self.timelines:
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

class ProxyCreator:
    def __init__(self, sockdir, sockfile='shareddict.sock'):
        self.sockaddr = os.path.join(sockdir, sockfile)
    
    def create_dict(self, objref):
        conn = connect(self.sockaddr)
        return DictProxy(objref, conn=conn)
        
    def create_timeline(self, objref):
        conn = connect(self.sockaddr)
        return TimelineProxy(objref, conn=conn)
    
    def create_timelines(self, objref):
        conn = connect(self.sockaddr)
        return TimelinesProxy(objref, conn=conn)

    def create_list(self, objref):
        conn = conn-ect(self.sockaddr)
        return ListProxy(objref, conn=conn)


def server(sockdir=None, sockfile='shareddict.sock', dofork=False, exitatclose=True):
    #nde = ServerDict()
    if sockdir == None:
        socketdirectory = tempfile.mkdtemp(prefix="epdb-shareddict-")
    else:
        socketdirectory = sockdir
    sockaddr = os.path.join(socketdirectory, sockfile)
    bplist = ServerDict()   # weird naming, but conforming to bdb
    bpbynumber = ServerList()
    bpbynumber.append(None)
    breaks = ServerDict()
    snapshots = ServerDict()
    resources_dict = {}
    managers_dict = {}

    nde_dict = {}
    ude_dict = {}

    # TODO rnext_dict and rcontinue_dict is likely not needed
    # In rnext the position for the rnext command to jump to is saved
    # It is filled in user_return
    rnext_dict = {}
    # In rcontinue for every executed line number a list of instruction counts
    # that have executed them is saved. This is needed for reverse continue
    rcontinue_dict = {}

    next_dict = {}
    continue_dict = {}

    #timelines = ServerTimelines(snapshots, nde_dict, ude_dict, rnext_dict, rcontinue_dict)
    timelines = ServerTimelines(snapshots, nde_dict, ude_dict, next_dict,
                                continue_dict, resources_dict, managers_dict
                                )
    #socketfile = '/tmp/shareddict'
    #try:
    #    os.unlink(sockfile)
    #except OSError:
    #    pass
    server = listen(sockaddr)
    if dofork:
        sdpid = os.fork() # TODO dofork returns when the server shutdowns?
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
                            m = re.match('^resources\.(?P<timeline>[^.]*)\.(?P<type>[^.]*)\.(?P<location>[^.]*)$', objref)
                            #manager_match = re.match('^managers\.(?P<timeline>[^.]*)\.(?P<type>[^.]*)\.(?P<location>[^.]*)$', objref)
                            #debug('matching done')
                            #if objref == 'nde':
                            #    r = getattr(nde, method)(*args, **kargs)
                            if objref == 'bplist':
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
                            elif objref.startswith('nde.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(nde_dict[id], method)(*args, **kargs)
                            elif objref.startswith('ude.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(ude_dict[id], method)(*args, **kargs)
                            elif objref.startswith('rnext.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(rnext_dict[id], method)(*args, **kargs)
                            elif objref.startswith('rcontinue.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(rcontinue_dict[id], method)(*args, **kargs)
                            elif objref.startswith('next.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(next_dict[id], method)(*args, **kargs)
                            elif objref.startswith('continue.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(continue_dict[id], method)(*args, **kargs)
                            #elif manager_match:
                            #    timeline = m.group('timeline')
                            #    typ = m.group('type')
                            #    location = str(base64.b64decode(bytes(m.group('location'), 'utf-8')), 'utf-8')
                            #    r = getattr(managers_dict[timeline][(typ, location)], method)(*args, **kargs)
                            #elif objref.startswith('managers.'):
                            #    id = '.'.join(objref.split('.')[1:])
                            #    r = getattr(managers_dict[id], method)(*args, **kargs)
                            elif m:
                                timeline = m.group('timeline')
                                typ = m.group('type')
                                location = str(base64.b64decode(bytes(m.group('location'), 'utf-8')), 'utf-8')
                                r = getattr(resources_dict[timeline][(typ, location)], method)(*args, **kargs)
                            elif objref.startswith('resources.'):
                                id = '.'.join(objref.split('.')[1:])
                                r = getattr(resources_dict[id], method)(*args, **kargs)
                            elif objref == 'control':
                                r = None
                                if method == 'shutdown':
                                    for c in connectiondict.values():
                                        if c != conn:
                                            c.close()
                                    conn.send(b'done')
                                    conn.close()
                                    do_quit = True
                        except Exception as e:
                            #debug("Remote Exception")
                            #traceback.print_exc()
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
    server.close()
    if sockdir == None: # delete tempdir if it was created
        os.unlink(tempdir)
    if exitatclose:
        sys.exit(0)

# TODO Fix it don't use /tmp/shareddict
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
    def __init__(self, objref, sockfile=None, conn=None):
        if sockfile:
            self.conn = connect(sockfile)
        if conn:
            self.conn = conn
            
        self.objref = objref

    def _remote_invoke(self, method, args, kargs):
        #debug("Dict Proxy/Remote invoke", self.objref, method, args, kargs, os.getpid())
        #fn = os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_back.f_back.f_code.co_filename)
        #lno = sys._current_frames()[_thread.get_ident()].f_back.f_back.f_back.f_lineno
        #fn2 = os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_back.f_code.co_filename)
        #lno2 = sys._current_frames()[_thread.get_ident()].f_back.f_back.f_lineno
        #fn3 = os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename)
        #lno3 = sys._current_frames()[_thread.get_ident()].f_back.f_lineno
        #debug('Filename: ', fn, lno, fn2, lno2, fn3, lno3)
        self.conn.send(pickle.dumps((self.objref, method, args, kargs)))
        recv = self.conn.recv()
        t,r = pickle.loads(recv)
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

    def keys(self): # this doesn't work
        return self._remote_invoke('keys',(), {})

    def values(self): # this doesn't work
        return self._remote_invoke('values',(), {})

    def get(self, k, d=None): # this doesn't work
        return self._remote_invoke('get',(k, d), {})

    def __len__(self):
        return self._remote_invoke('__len__',(), {})

    def clear(self):
        return self._remote_invoke('clear',(), {})

    def close(self):
        self.conn.close()

class ListProxy:
    def __init__(self, objref, sockfile=None, conn=None):
        if sockfile:
            self.conn = connect(sockfile)
        if conn:
            self.conn = conn
            
        self.conn = connect(sockfile)
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

    def __len__(self):
        return self._remote_invoke('__len__',(), {})

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

    def close(self):
        self.sock.close()

class TimelineProxy:
    def __init__(self, objref, sockfile=None, conn=None):
        if sockfile:
            self.conn = connect(sockfile)
        if conn:
            self.conn = conn
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

    def get_nde(self):
        objref = self._remote_invoke('get_nde',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_ude(self):
        objref = self._remote_invoke('get_ude',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_rnext(self):
        objref = self._remote_invoke('get_rnext',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_rcontinue(self):
        objref = self._remote_invoke('get_rcontinue',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_next(self):
        objref = self._remote_invoke('get_next',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_continue(self):
        objref = self._remote_invoke('get_continue',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def deactivate(self, ic):
        return self._remote_invoke('deactivate',(ic,), {})

    def get_ic(self):
        return self._remote_invoke('get_ic',(), {})

    def get_max_ic(self):
        return self._remote_invoke('get_max_ic',(), {})

    def set_max_ic(self, maxic):
        return self._remote_invoke('set_max_ic',(maxic,), {})

    def get_snapshots(self):
        return self._remote_invoke('get_snapshots',(), {})

    def get_resource(self, type, location):
        #debug('get_resource')
        objref = self._remote_invoke('get_resource',(type,location), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def get_resources(self):
        objref = self._remote_invoke('get_resources',(), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def new_resource(self, type, location):
        #debug('new resource')
        objref = self._remote_invoke('new_resource',(type, location), {})
        proxy = DictProxy(objref=objref, conn=self.conn)
        return proxy

    def create_manager(self, identification, manager):
        """identification is a tuple (type, location)"""
        return self._remote_invoke('create_manager',(identification, manager), {})

    def get_manager(self, identification):
        return self._remote_invoke('get_manager',(identification,), {})

    def update_manager(self, identification, manager):
        return self._remote_invoke('update_manager',(identification, manager), {})

    def update_stdout_cache(self, text):
        return self._remote_invoke('update_stdout_cache',(text,), {})

    def get_stdout_cache(self):
        return self._remote_invoke('get_stdout_cache',(), {})

    def set_stdout_cache(self, text):
        return self._remote_invoke('set_stdout_cache',(text,), {})

    def close(self):
        self.sock.close()

class TimelinesProxy:
    def __init__(self, objref, sockfile=None, conn=None):
        if sockfile:
            self.conn = connect(sockfile)
        if conn:
            self.conn = conn
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

    def close(self):
        self.conn.close()

def shutdown(sockdir, sockfilename="shareddict.sock"):
    sockaddr = os.path.join(sockdir, sockfilename)
    conn = connect(sockaddr)
    conn.send(pickle.dumps(('control', 'shutdown', (), {})))
    done = conn.recv()
    if done == b'done':
        conn.close()
    else:
        print("Error", done)

if __name__ == '__main__':
    server(dofork=True)
    tls = TimelinesProxy("timelines", dbg.shareddict_sock)
    tl = tls.new_timeline()
    tls.show()
    tl.show()
    shutdown(dbg.shareddict_sock)
