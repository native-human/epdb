#!/usr/bin/env python

# TODO make this file look more like in the thesis

import builtins
import types
import dbg
from io import SEEK_SET, SEEK_END, SEEK_CUR
import io
import os
import os.path
import sys
import _thread
from uuid import uuid4
import debug as log
import shelve
import base64
import traceback
import resources

def orig_open(*args, **kargs):
    return builtins.__orig__open(*args, **kargs)

def print(*args, sep=' ', end='\n', file=sys.stdout):
    if dbg.is_dbg_callee():
        return builtins.__orig__print(*args, sep=sep, end=end, file=file)
    if dbg.mode == 'replay' or dbg.mode == 'redo':
        return None
    elif dbg.mode == 'normal':
        s = io.StringIO()
        builtins.__orig__print(*args, sep=sep, end=end, file=s)
        dbg.stdout_resource_manager.update_stdout(s.getvalue())
        id = dbg.stdout_resource_manager.save()
        dbg.current_timeline.get_resource('__stdout__', '')[dbg.ic+1] = id
        return builtins.__orig__print(*args, sep=sep, end=end, file=file)

def input(prompt=""):
    caller = os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename)
    if caller in ['cmd.py']:
        return builtins.__orig__input(prompt)
    if dbg.mode == 'redo' or dbg.mode == 'replay':
        return None
    elif dbg.mode == 'normal':
        dbg.snapshottingcontrol.set_make_snapshot()
        log.debug("expect input#")
        orig = builtins.__orig__input(prompt)
        dbg.stdout_resource_manager.update_stdout(prompt + orig + '\r\n')
        id = dbg.stdout_resource_manager.save()
        dbg.current_timeline.get_resource('__stdout__', '')[dbg.ic+1] = id
        return orig

class FileProxy:
    def __init__(self, file, args):
        self.__file__ = file
        self._args = args
        self.fn = fn = args[0]
        resource = dbg.current_timeline.new_resource('file', fn)
        rm = resources.FileResourceManager(self.fn)
        self._fileresourcemanager = dbg.current_timeline.create_manager(('file',fn),rm)
        id = self._fileresourcemanager.save()
        if not dbg.ic in resource:
            resource[dbg.ic] = id

    def write(self, b):
        if dbg.mode == 'normal':
            value = self.__file__.write(b)
            id = self._fileresourcemanager.save()
            dbg.current_timeline.get_resource('file', self.fn)[dbg.ic+1] = id
            dbg.snapshottingcontrol.set_make_snapshot()
            return value
        elif dbg.mode == 'replay' or dbg.mode == 'redo':
            "This should never happen"
            #value = self.__file__.write(b)
        
    def read(self, n=-1):
        if dbg.mode == 'normal':
            dbg.snapshottingcontrol.set_make_snapshot()
            value = self.__file__.read(n)
            return value
        # else: "This should never happen because of forward activation"
   
    def close(self):
        if dbg.mode == 'normal':
            self.__file__.close()
            id = self._fileresourcemanager.save()
            dbg.current_timeline.get_resource('file', self.fn)[dbg.ic+1] = id
        elif dbg.mode == 'replay' or dbg.mode == 'redo':
            self.__file__.close()

def open(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
    if dbg.is_dbg_callee():
        return builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)

    fd = builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
    args = (file, mode, buffering, encoding, errors, newline, closefd)
    fp = FileProxy(fd, args)
    return fp