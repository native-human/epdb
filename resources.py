#!/usr/bin/env python

import shelve
import base64
import os.path
import tempfile
import dbg
import builtins
from fcntl import LOCK_SH, LOCK_EX, LOCK_UN, LOCK_NB
import fcntl
from uuid import uuid4
from debug import debug


def _close(self):
    shelve.Shelf.close(self)
    fcntl.flock(self.lckfile.fileno(), LOCK_UN)
    self.lckfile.close()

def safe_shelve_open(filename, flag='c', protocol=None, writeback=False, block=True, lckfilename=None):
    """Open the sheve file, createing a lockfile at filename.lck.  If 
    block is False then a IOError will be raised if the lock cannot
    be acquired"""
    if lckfilename == None:
        lckfilename = filename + ".lck"
    lckfile = open(lckfilename, 'w')

    if flag == 'r':
        lockflags = LOCK_SH
    else:
        lockflags = LOCK_EX
    if not block:
        lockflags |= LOCK_NB
    fcntl.flock(lckfile.fileno(), lockflags)

    shelf = shelve.open(filename, flag, protocol, writeback)
    shelf.close = _close.__get__(shelf, shelve.Shelf)
    shelf.lckfile = lckfile 
    return shelf


def orig_open(*args, **kargs):
    return builtins.__orig__open(*args, **kargs)

class StdoutResourceManager:
    def __init__(self, shelvename=None, stdout_cache=None):
        tempdir = dbg.tempdir
        if shelvename:
            self.shelvename = shelvename
        else:
            self.shelvename = os.path.join(tempdir, "__stdout__")
        
        if stdout_cache:
            self.stdout_cache = stdout_cache
        else:
            self.stdout_cache = ""
            
    def save(self):
        id = uuid4().hex
        #db = shelve.open(self.shelvename)
        debug("stdout save shelve open")
        db = safe_shelve_open(self.shelvename)
        db[id] = self.stdout_cache
        db.close()
        debug("stdout save shelve closed")
        return id

    def restore(self, id):
        debug("stdout restore shelve open")
        db = safe_shelve_open(self.shelvename)
        self.stdout_cache = db[id]
        debug("stdout restore shelve closed")
        db.close()
        debug("-->")
        debug(self.stdout_cache, prefix="#->", end='')
        
        
    def update_stdout(self, output):
        self.stdout_cache += output
        
    def __reduce__(self):
        return (StdoutResourceManager, (self.shelvename, self.stdout_cache))       
    
class FileResourceManager:
    def __init__(self, filename):
        #debug('fileresource manager')
        tempdir = dbg.tempdir
        #tempdir = tempfile.mkdtemp()
        shelvename = os.path.join(tempdir,
                str(base64.b32encode(bytes(filename,'utf-8')),'utf-8')
            )
        self.shelvename = shelvename
        #shelvename = os.path.join('/tmp',
        #        str(base64.b32encode(bytes(filename,'utf-8')),'utf-8')
        #    )
        #debug('shelvename worked', shelvename)
        #try:
        #    self.db = shelve.open(shelvename)
        #except:
        #    traceback.print_exc()
        self.filename = filename
        #debug('shelve open worked')
    
    def save(self):
        id = uuid4().hex
        debug("File save shelve open")
        db = safe_shelve_open(self.shelvename)
        db[id] = orig_open(self.filename).read()
        #debug("FILE SAVED", repr(db[id]))
        db.close()
        debug("File save shelve closed")
        #print("SAVE done", id)
        return id
    
    def restore(self, id):
        debug("File restore shelve open")
        db = safe_shelve_open(self.shelvename)
        content = db[id]
        db.close()
        debug("File restore shelve closed")
        #content = self.db[id]
        debug('RESTORE CONTENT: ', repr(content),"ID", id)
        with orig_open(self.filename, 'w') as f:
            f.write(content)
        
    def __reduce__(self):
        return (FileResourceManager, (self.filename,))
    
if __name__ == '__main__':
    import pickle
    r = FileResourceManager("filename")
    d = pickle.dumps(r)
    print(d)
    o = pickle.loads(d)
    print(o.filename)