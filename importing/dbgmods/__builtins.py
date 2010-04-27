#!/usr/bin/env python

import builtins
import types
import __dbg as dbg
from io import SEEK_SET, SEEK_END, SEEK_CUR
import os
import sys
import _thread

class FileProxy:
    def __init__(self, file):
        self.__file__ = file
        self.__action_hist__ = []
    def write(self, b):
        def replay(self, b):
            return self.__orig__write(b)
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
                print('Undo writing file')
                self.__file__.seek(origposition, SEEK_SET)
                self.__file__.write(overwritten)
                self.__file__.truncate(filesize)
            dbg.sde[dbg.ic] = {'afterposition':afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            return value
        print('Writing to the file descriptor')
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
                print('Undoing read')
                self.__file__.seek(origposition, SEEK_SET)
            self.__action_hist__.append(('read',value, None))
            dbg.sde[dbg.ic] = {'afterposition': afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            print('Saving redoing function on', dbg.ic)
            return value
        def replay(self, n):
            d = dbg.sde[dbg.ic]
            afterposition = d['afterposition']
            value = d['value']
            self.__file__.seek(afterposition, SEEK_SET)
            return value
            #print('Position: ', dbg.ic)
            #return dbg.sde[dbg.ic]()
        print('reading from the file descriptor')
        #sys._current_frames()[thread.get_ident()].f_code.co_filename
        if dbg.mode == 'normal':
            return debug(self, n)
        if dbg.mode == 'replay':
            return replay(self,n)
    
    def close(self):
        def debug(self):
            print('Doing close')
            self.__file__.close()
            self.__action_hist__.append(('close',None, None))
            dbg.ude[dbg.ic] = undo
        def replay(self):
            print('Replaying close')
            self.__file__.close()
        def undo():
            idx = len(self.__action_hist__)
            print(idx)
            while idx > 0:
                idx -= 1
                cmd,new,old = self.__action_hist__[idx]
                if cmd == 'flush' or cmd == 'open':
                    break
            
            assert cmd == 'flush' or cmd == 'open'    
            
            while idx < len(self.__action_hist__)-1:
                cmd,new,old = self.__action_hist__[idx]
                if cmd == 'flush' or cmd == 'open':
                    self.__file__.seek(0, SEEK_SET)
                    self.__file__.write(new)
                    print('Closing: resetted to last flush')
                if cmd == 'write':
                    self.__file__.write(new)
                    print('Closing: rewritten')
                if cmd == 'read':
                    self.__file__.seek(len(new), SEEK_CUR)
                    print('Closing: rereading')
                idx += 1
            
            print('Undoing close')
        if dbg.mode == 'normal':
            return debug(self)
        elif dbg.mode == 'replay':
            return replay(self)
    
def open(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
    # Functions to supersed the file descriptor methods
    def fdwrite(self, b):
        def replay(self, b):
            #d = dbg.sde[dbg.ic]
            #afterposition = d['afterposition']
            #value = d['value']
            #self.seek(afterposition, SEEK_SET)
            #return value
            #return dbg.sde[dbg.ic]()
            return self.__orig__write(b)
        def debug(self, b):
            
            origposition = self.tell()
            # get the file size
            self.seek(0, SEEK_END)
            filesize = self.tell()
            #
            self.seek(origposition, SEEK_SET)
            
            overwritten = self.__orig__read(len(b))
            self.seek(origposition, SEEK_SET)
            afterposition = self.tell()
            value = self.__orig__write(b)
            self.__action__hist.append(('write',b, overwritten))
            def undoer():
                print('Undo writing file')
                self.seek(origposition, SEEK_SET)
                self.write(overwritten)
                self.truncate(filesize)
            #def redo():
            #    self.seek(afterposition, SEEK_SET)
            #    return value
            #dbg.sde[dbg.ic] = redo
            dbg.sde[dbg.ic] = {'afterposition':afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            return value
        print('Writing to the file descriptor')
        if dbg.mode == 'normal':
            return debug(self, b)
        elif dbg.mode == 'replay':
            return replay(self, b)
    def fdread(self, n = -1):
        def debug(self, n):
            origposition = self.tell()
            value = self.__orig__read(n)
            afterposition = self.tell()
            def undoer():
                print('Undoing read')
                self.seek(origposition, SEEK_SET)
            #def redo():
            #    print('Redoing read')
            #    self.seek(afterposition, SEEK_SET)
            #    return value
            #dbg.sde[dbg.ic] = redo
            self.__action__hist.append(('read',value, None))
            dbg.sde[dbg.ic] = {'afterposition': afterposition, 'value': value}
            dbg.ude[dbg.ic] = undoer
            print('Saving redoing function on', dbg.ic)
            return value
        def replay(self, n):
            d = dbg.sde[dbg.ic]
            afterposition = d['afterposition']
            value = d['value']
            self.seek(afterposition, SEEK_SET)
            return value
            #print('Position: ', dbg.ic)
            #return dbg.sde[dbg.ic]()
        print('reading from the file descriptor')
        #sys._current_frames()[thread.get_ident()].f_code.co_filename
        if dbg.mode == 'normal':
            return debug(self, n)
        if dbg.mode == 'replay':
            return replay(self,n)
    def fdclose(self):
        def debug(self):
            print('Doing close')
            self.__orig__close()
            self.__action__hist.append(('close',None, None))
            dbg.ude[dbg.ic] = undo
        def replay(self):
            print('Replaying close')
            self.__orig__close()
        def undo():
            idx = len(self.__action__hist)
            print(idx)
            while idx > 0:
                idx -= 1
                cmd,new,old = self.__action__hist[idx]
                if cmd == 'flush' or cmd == 'open':
                    break
            
            assert cmd == 'flush' or cmd == 'open'    
            
            while idx < len(self.__action__hist)-1:
                cmd,new,old = self.__action__hist[idx]
                if cmd == 'flush' or cmd == 'open':
                    self.seek(0, SEEK_SET)
                    self.write(new)
                    print('Closing: resetted to last flush')
                if cmd == 'write':
                    self.__orig__write(new)
                    print('Closing: rewritten')
                if cmd == 'read':
                    self.seek(len(new), SEEK_CUR)
                    print('Closing: rereading')
                idx += 1
            
            print('Undoing close')
        if dbg.mode == 'normal':
            return debug(self)
        elif dbg.mode == 'replay':
            return replay(self)
            
   
    # Replay and debug for the open call
    def replay(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        return debug(file, mode, buffering, encoding, errors, newline, closefd)
    def undo(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        pass
    def debug(file, mode = "r", buffering = -1, encoding = None, errors = None, newline = None, closefd = True):
        print('Debug open')
        writeonly = readonly = False
        if 'r' in mode and not '+' in mode:
            readonly = True
        
        if ('w' in mode or 'a' in mode) and not '+' in mode:
            writeonly = True
            print('Warning: writeonly opening of a file cannot be debugged in reverse')
        
        fd = builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
        fp = FileProxy(fd)
        startbuffer = fd.read()
        fd.seek(0, SEEK_SET)
        fp.__action_hist__.append(('open',startbuffer, None)) 
        def undoer():
            print('Undo opening file')
            fd.close()
        dbg.ude[dbg.ic] = undoer
        
        return fp
            
            
        fd = builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
        fd.__orig__write = fd.write
        fd.write = types.MethodType(fdwrite, fd)
        fd.__orig__read = fd.read
        fd.read = types.MethodType(fdread, fd)
        fd.__orig__close = fd.close
        fd.close = types.MethodType(fdclose, fd)
        fd.__file__ = file
        
        fd.__action__hist = []
        startbuffer = fd.read()
        fd.seek(0, SEEK_SET)
        fd.__action__hist.append(('open',startbuffer,None))
        
        def undoer():
            print('Undo opening file')
            fd.close()
        dbg.ude[dbg.ic] = undoer
        #print(dbg.ude)
        #try:    
        #    dbg.ude[dbg.ic] = 'kd'
        #except TypeError as e:
        #    print('TypeError: ', str(e))
        #print('ok')
        return fd
    
    print('Caller:', os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename))
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'linecache.py']:
        return builtins.__orig__open(file, mode, buffering, encoding, errors, newline, closefd)
    if dbg.mode == 'replay':
        return replay(file, mode, buffering, encoding, errors, newline, closefd)
    elif dbg.mode == 'normal':
        return debug(file, mode, buffering, encoding, errors, newline, closefd)
    elif dbg.mode == 'undo':
        return undo(file, mode, buffering, encoding, errors, newline, closefd)