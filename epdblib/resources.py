#!/usr/bin/env python

import shelve
import base64
import os.path
import tempfile
from epdblib import dbg
import builtins
from fcntl import LOCK_SH, LOCK_EX, LOCK_UN, LOCK_NB
import fcntl
from uuid import uuid4
from epdblib.debug import debug

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
        tempdir = os.path.join(dbg.tempdir, "stdout_resource")
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
        db = safe_shelve_open(self.shelvename)
        db[id] = dbg.current_timeline.get_stdout_cache()
        db.close()
        return id

    def restore(self, id):
        db = safe_shelve_open(self.shelvename)
        cache = db[id]
        dbg.current_timeline.set_stdout_cache(cache)
        db.close()
        dbg.dbgcom.send_stdout(cache)

    def update_stdout(self, output):
        dbg.current_timeline.update_stdout_cache(output)
        
    def __reduce__(self):
        return (StdoutResourceManager, (self.shelvename, self.stdout_cache))

class FileResourceManager:
    def __init__(self, filename):
        tempdir = os.path.join(dbg.tempdir, "file_resource")
        shelvename = os.path.join(tempdir,
                str(base64.b32encode(bytes(filename,'utf-8')),'utf-8')
            )
        self.shelvename = shelvename
        self.filename = filename

    def save(self):
        id = uuid4().hex
        db = safe_shelve_open(self.shelvename)
        db[id] = orig_open(self.filename).read()
        db.close()
        return id

    def restore(self, id):
        db = safe_shelve_open(self.shelvename)
        content = db[id]
        db.close()
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
