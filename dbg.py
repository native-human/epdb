#!/usr/bin/env python
import os
import os.path
import sys
import _thread

def is_dbg_callee():
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_back.f_code.co_filename) in ['epdb.py', 'debug.py', 'pdb.py', 'linecache.py', 'resources.py', "asyncmd.py", "configparser.py", "posixpath.py"]:
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
