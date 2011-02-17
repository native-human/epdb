
import shelve
import base64
import os.path
import tempfile
from fcntl import LOCK_SH, LOCK_EX, LOCK_UN, LOCK_NB
import fcntl
from uuid import uuid4


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

s1 = safe_shelve_open("/tmp/test",'c',block=False)
s2 = safe_shelve_open('/tmp/test','c',block=False)
s1[x] = "sdfksadfjsd"
s2[x] = "kdfslksadfjldsf"
s1.close()
s2.close()
