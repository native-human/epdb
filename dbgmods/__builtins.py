#!/usr/bin/env python

import builtins
import types
import __dbg as dbg
from io import SEEK_SET, SEEK_END, SEEK_CUR
import os
import sys
import _thread
import debug as log

def orig_open(*args, **kargs):
    return builtins.__orig__open(*args, **kargs)

class FileProxy:
    def __init__(self, file, args):
        self.__file__ = file
        self.__action_hist__ = []
        self._args = args
    def write(self, b):
        def replay(self, b):
            return debug(self, b)
        def debug(self, b):
            
            origposition = self.__file__.tell()
            # get the file size
            self.__file__.seek(0, SEEK_END)
            filesize = self.__file__.tell()
            #
            self.__file__.seek(origposition, SEEK_SET)
            
            overwritten = self.__file__.read(len(b))
            self.__file__.seek(origposition, SEEK_SET)
            afterposition = self.__file__.tell()
            value = self.__file__.write(b)
            self.__action_hist__.append(('write',b, overwritten))
            def undoer():
                log.debug('Undo writing file')
                self.__file__.seek(origposition, SEEK_SET)
                self.__file__.write(overwritten)
                self.__file__.truncate(filesize)
            dbg.sde[dbg.ic] = {'afterposition':afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            return value
        log.debug('Writing to the file descriptor')
        if dbg.mode == 'normal':
            return debug(self, b)
        elif dbg.mode == 'replay':
            return replay(self, b)
    
    def read(self, n=-1):
        def debug(self, n):
            origposition = self.__file__.tell()
            value = self.__file__.read(n)
            afterposition = self.__file__.tell()
            def undoer():
                log.debug('Undoing read')
                self.__file__.seek(origposition, SEEK_SET)
            self.__action_hist__.append(('read',value, None))
            dbg.sde[dbg.ic] = {'afterposition': afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            log.debug('Saving redoing function on', dbg.ic)
            return value
        def replay(self, n):
            d = dbg.sde[dbg.ic]
            afterposition = d['afterposition']
            value = d['value']
            self.__file__.seek(afterposition, SEEK_SET)
            return value
            #log.debug('Position: ', dbg.ic)
            #return dbg.sde[dbg.ic]()
        log.debug('reading from the file descriptor')
        #sys._current_frames()[thread.get_ident()].f_code.co_filename
        if dbg.mode == 'normal':
            return debug(self, n)
        if dbg.mode == 'replay':
            return replay(self,n)
    
    def close(self):
        def debug(self):
            log.debug('Doing close')
            self.__file__.close()
            self.__action_hist__.append(('close',None, None))
            dbg.ude[dbg.ic] = undo
        def replay(self):
            log.debug('Replaying close')
            self.__file__.close()
        def undo():
            idx = len(self.__action_hist__)
            log.debug(idx)
            while idx > 0:
                idx -= 1
                cmd,new,old = self.__action_hist__[idx]
                if cmd == 'flush' or cmd == 'open':
                    break
            
            assert cmd == 'flush' or cmd == 'open'
            self.__file__ = orig_open(*self._args)
            
            while idx < len(self.__action_hist__)-1:
                cmd,new,old = self.__action_hist__[idx]
                if cmd == 'flush' or cmd == 'open':
                    self.__file__.seek(0, SEEK_SET)
                    self.__file__.write(new)
                    log.debug('Closing: resetted to last flush:', new)
                if cmd == 'write':
                    self.__file__.write(new)
                    log.debug('Closing: rewritten')
                if cmd == 'read':
                    pos = self.__file__.tell()
                    self.__file__.seek(pos + len(new), SEEK_SET)
                    log.debug('Closing: rereading')
                idx += 1
            
            log.debug('Undoing close')
        if dbg.mode == 'normal':
            return debug(self)
        elif dbg.mode == 'replay':
            return replay(self)
    
def open(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
    # Replay and debug for the open call
    def replay(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        return debug(file, mode, buffering, encoding, errors, newline, closefd)
    def undo(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        pass
    def debug(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        log.debug('Debug open')
        writeonly = readonly = False
        if 'r' in mode and not '+' in mode:
            readonly = True
        
        if ('w' in mode or 'a' in mode) and not '+' in mode:
            writeonly = True
            log.debug('Warning: writeonly opening of a file cannot be debugged in reverse')
        
        fd = builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
        args = (file, mode, buffering, encoding, errors, newline, closefd)
        fp = FileProxy(fd, args)
        startbuffer = fd.read()
        fd.seek(0, SEEK_SET)
        fp.__action_hist__.append(('open',startbuffer, None)) 
        def undoer():
            log.debug('Undo opening file')
            fd.close()
        dbg.ude[dbg.ic] = undoer
        
        return fp
    
    log.debug('Caller:', os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename))
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'linecache.py']:
        return builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
    if dbg.mode == 'replay':
        return replay(file, mode, buffering, encoding, errors, newline, closefd)
    elif dbg.mode == 'normal':
        return debug(file, mode, buffering, encoding, errors, newline, closefd)
    elif dbg.mode == 'undo':
        return undo(file, mode, buffering, encoding, errors, newline, closefd)