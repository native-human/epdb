import sys
import imp
import os
import os.path

class EpdbImportFinder:
    def __init__(self, path=None, dbgmods=[], debugger=None):
        if path is not None and not os.path.isdir(path):
            raise ImportError
        self.path = path
        self.debugger = debugger
        self.dbgmods = dbgmods

    def find_module(self, fullname, path=None):
        patchfilename = None
        
        subname = fullname.split(".")[-1]
        
        splitted_name = ["__" + e for e in fullname.split(".")]
        patchmodname = ".".join(splitted_name)
        patchpath = None
        for dbgpath in self.dbgmods:
            patchpath = os.path.join(os.path.abspath(dbgpath), *splitted_name)
            if os.path.exists(patchpath):
                break
            elif os.path.exists(patchpath+'.py'):
                patchfilename = patchpath+'.py'
                break
            elif os.path.exists(patchpath+".pyc"):
                break
            else:
                pass
        else: # No patch file found"
            return # use standard import mechanism if no patch module exists
        if self.debugger:
            self.debugger.add_skip_module(fullname)
        
        if subname != fullname and self.path is None:
            try:
                file, filename, stuff = imp.find_module(subname, path)
            except ImportError:
                return None
            
            return EpdbImportLoader(file, filename, stuff,
                            patchfilename=patchfilename, debugger=self.debugger)
        if self.path is None:
            path = None
        else:
            path = [self.path]
        try:
            file, filename, stuff = imp.find_module(subname, path)
        except ImportError:
            return None
        return EpdbImportLoader(file, filename, stuff,
                                patchfilename=patchfilename, debugger=self.debugger)

class EpdbImportLoader:    
    def __init__(self, file, filename, stuff, patchfilename=None, debugger=None):
        self.file = file
        self.filename = filename
        self.stuff = stuff
        self.debugger = debugger
        self.patchfilename = patchfilename

    def load_module(self, fullname):
        mod = imp.load_module(fullname, self.file, self.filename, self.stuff)
        if self.file:
            self.file.close()
        mod.__loader__ = self  # for introspection
        if self.patchfilename:
            with open(self.patchfilename) as patchfile:
                exec(patchfile.read(), mod.__dict__)
        return mod