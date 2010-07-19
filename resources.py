#!/usr/bin/env python

import shelve
import base64
import os.path
import tempfile
from uuid import uuid4
from debug import debug

class FileResourceManager:
    def __init__(self, filename, history={}):
        debug('fileresource manager')
        tempdir = dbg.tempdir
        #tempdir = tempfile.mkdtemp()
        shelvename = os.path.join(tempdir,
                str(base64.b32encode(bytes(filename,'utf-8')),'utf-8')
            )
        #shelvename = os.path.join('/tmp',
        #        str(base64.b32encode(bytes(filename,'utf-8')),'utf-8')
        #    )
        debug('shelvename worked', shelvename)
        try:
            self.db = shelve.open(shelvename)
        except:
            traceback.print_exc()
        debug('shelve open worked')
        self.filename = filename
        self.history = history
    
    def save(self):
        id = uuid4().hex
        self.db[id] = orig_open(self.filename).read()
        return id
    
    def restore(self, id):
        content = self.dict[id]
        with orig_open(self.filename, 'w') as f:
            f.write(content)
        
    def __reduce__(self):
        return (FileResourceManager, (self.filename, self.history))
    
if __name__ == '__main__':
    import pickle
    r = FileResourceManager("filename")
    d = pickle.dumps(r)
    print(d)
    o = pickle.loads(d)
    print(o.filename)