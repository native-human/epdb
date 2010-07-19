#!/usr/bin/env python

import shelve
import base64
import os.path
import tempfile
import dbg
import builtins
from uuid import uuid4
from debug import debug

def orig_open(*args, **kargs):
    return builtins.__orig__open(*args, **kargs)

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
        db = shelve.open(self.shelvename)
        db[id] = orig_open(self.filename).read()
        db.close()
        print("SAVE done", id)
        return id
    
    def restore(self, id):
        db = shelve.open(self.shelvename)
        content = db[id]
        db.close()
        #content = self.db[id]
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