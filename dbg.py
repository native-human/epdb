#!/usr/bin/env python
#from multiprocessing.managers import BaseManager
#from multiprocessing.managers import BaseProxy
import os
#import multiprocessing.util

#multiprocessing.util.log_to_stderr()

#class IdGenerator:
#    def __init__(self):
#        self.id = 0
#    def newid(self):
#        r = self.id
#        self.id += 1
#        return r
#    
#idgenerator = IdGenerator()

class SnapshottingControl:
    def __init__(self):
        self._make_snapshot = False
    def set_make_snapshot(self):
        self._make_snapshot = True
        
    def get_make_snapshot(self):
        return self._make_snapshot
    
    def clear_make_snapshot(self):
        self._make_snapshot = False

snapshottingcontrol = SnapshottingControl()

timelines = None

current_timeline = None

# The stdout resource
stdout_resource = None
stdout_resource_manager = None

# tempdir is the temporary file used by all the processes. tempdir is setted on startup.
tempdir = None

# mode can be of 'normal', 'replay', 'redo', 'undo'
mode = 'normal'

# nde ... side effects dictionary ic:effect effect is a function
# Will be overwritten by an proxy to the manager
nde = {}

# ude ... undo effects dictionary ic:effect effect is a function
ude = {}

# undod
# Will be overwritten by an Proxy
undod = {}

#manager = None
#server = None

modules = []

ic = 0
# maximum ic in current timeline.

#server_n
de = {}
#server_ude = {}

#dict = None

#class DictManager(BaseManager):
#    pass
#
#def get_nde():
#    return server_nde


#DictManager.register('get_ude', callable=lambda:server_ude, proxytype=DictProxy)
#
#def start_server():
#    class DictProxy(BaseProxy):
#        _exposed_ = ['__getitem__', '__setitem__','__str__','__repr__']
#        def __getitem__(self, value):
#            ret = self._callmethod('__getitem__',(value,))
#            return ret
#        def __setitem__(self, idx, value):
#            self._callmethod('__setitem__',(value,))
#        def __repr__(self):
#            return self._callmethod('__repr__')
#        def __str__(self):
#            return self._callmethod('__str__')
#    
#    d = {}
#    def getdict():
#        return d
#    
#    if os.fork():
#        class DictManager(BaseManager):
#            pass
#        DictManager.register('dict', getdict, proxytype=DictProxy)
#        m = DictManager(address=('', 50000), authkey=b'epdb')
#        s = m.get_server()
#        s.serve_forever()
#        sys.exit(0)    
#    
#def connect():
#    global manager
#    global dict
#    DictManager.register('dict')
#    #dict = m.get_dict()
#    #dict[123] = {}
#    manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
#    manager.connect()
#    dict = manager.dict()
#    
#if __name__ == '__main__':   
#    import sys
#    import os
#    import time
#    from multiprocessing.managers import BaseManager
#    from multiprocessing.managers import BaseProxy
#    
#    start_server()
#    
#    #class DictProxy(BaseProxy):
#    #    _exposed_ = ['__getitem__', '__setitem__','__str__','__repr__']
#    #    def __getitem__(self, value):
#    #        ret = self._callmethod('__getitem__',(value,))
#    #        return ret
#    #    def __setitem__(self, idx, value):
#    #        self._callmethod('__setitem__',(value,))
#    #    def __repr__(self):
#    #        return self._callmethod('__repr__')
#    #    def __str__(self):
#    #        return self._callmethod('__str__')
#    #
#    #d = {}
#    #def getdict():
#    #    return d
#    #
#    #if os.fork():
#    #    class DictManager(BaseManager):
#    #        pass
#    #    DictManager.register('dict', getdict, proxytype=DictProxy)
#    #    m = DictManager(address=('', 50000), authkey=b'epdb')
#    #    s = m.get_server()
#    #    s.serve_forever()
#    #    sys.exit(0)
#    
#    time.sleep(0.5)
#    #
#    DictManager.register('dict')
#    #dict = m.get_dict()
#    #dict[123] = {}
#    manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
#    manager.connect()
#    nde = manager.dict()
#    #connect()

#    if os.fork():
#        nde[1] = 'hallo Welt'
#        nde[2] = 'Number2'
#        time.sleep(3)
#    else:
#        #connect()
#        #del m
#        #del nde
#        time.sleep(1)
#        manager = DictManager(address=('localhost', 50000), authkey=b'epdb')
#        manager.connect()
#        nde = manager.dict()
#        time.sleep(0.5)
#        nde[3] = 'Blah'
#        print('done', nde, nde[1])