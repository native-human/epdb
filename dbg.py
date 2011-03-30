#!/usr/bin/env python
import os
import os.path
import sys
import _thread

epdb_modules = ['epdb.py', 'debug.py', 'pdb.py', 'linecache.py', 'resources.py', "asyncmd.py", "configparser.py", "posixpath.py"]
skipped_modules = ['time', 'debug', 'fnmatch', 'epdb',
                'posixpath', 'shareddict', 'pickle', 'os', 'dbg', 'locale',
                'codecs', 'types', 'io', 'builtins', 'ctypes', 'linecache',
                'uuid', 'shelve', 'collections', 'tempfile', '_thread',
                'subprocess', 're', 'sre_parse', 'struct', 'ctypes',
                'threading', 'ctypes._endian', 'copyreg', 'ctypes.util',
                'sre_compile', 'abc', '_weakrefset', 'base64', 'dbm',
                'traceback', 'tokenize', 'dbm.gnu', 'dbm.ndbm', 'dbm.dumb',
                'functools', 'resources', 'bdb', 'debug', 'runpy', 'genericpath',
                'encodings.ascii', 'configparser', 'itertools', 'copy', 'linecache',
                'mimetypes', 'urllib.parse', 'urllib', 'inspect', 'dis', 'opcode',
                'textwrap', 'http', 'http.client', 'email', 'email.parser',
                'email.feedparser', 'email.errors', 'email.message', 'uu',
                'email.utils', 'email._parseaddr', 'quopri', 'email.encoders',
                'email.charset', 'email.base64mime', 'email.quoprimime',
                'email.iterators', 'ssl', 'urllib.request', 'hashlib',
                'urllib.error', 'urllib.response', '_abcoll', 'pkg_resources',
                'distutils', 'distutils.util', 'distutils.errors',
                'distutils.dep_util', 'distutils.spawn', 'distutils.log',
                'distutils.core', 'pkgutil', 'stat', 'encodings', 'socket',
                'encodings.idna', 'stringprep', 'json', 'json.decoder',
                'json.scanner', 'json.encoder', 'epdblib.importer', 'couchdb',
                'couchdb.client', 'inspect', 'encodings.latin_1', 'couchdb.http',
                'couchdb.json', 'calendar', 'decimal', 'numbers']

def is_dbg_callee():
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_back.f_code.co_filename) in epdb_modules:
        return True
    return False

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

dbgcom = None

timelines = None

current_timeline = None

# The stdout resource
#stdout_resource = None
#stdout_resource_manager = None

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

stdout_cache = ''

ic = 0
# maximum ic in current timeline.

# modules to skip at next user_line
skip_modules = set([])
