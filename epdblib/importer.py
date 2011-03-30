import sys
import imp
import os
#import time

class EpdbImportFinder:
    def __init__(self, path=None, dbgmods=[], debugger=None):
        if path is not None and not os.path.isdir(path):
            raise ImportError
        self.path = path
        self.debugger = debugger
        self.dbgmods = dbgmods

    def find_module(self, fullname, path=None):
        #if fullname in ['inspect', 'pkg_resources', 'mimetypes', 'textwrap']:
        #    return None
        #print("[find_module]", fullname)
        patchfilename = None
        
        subname = fullname.split(".")[-1]
        #print("[findmodule]", "subname:", subname, "fullname:", fullname, "path:", path)
        
        #loaded_spam_modules = [mod for mod in sys.modules.keys() if mod.startswith("spam")]
        #print("loaded_modules:", loaded_spam_modules)
        
        splitted_name = ["__" + e for e in fullname.split(".")]
        patchmodname = ".".join(splitted_name)
        #print("patchmodname:", patchmodname)
        patchpath = None
        for dbgpath in self.dbgmods:
            patchpath = os.path.join(os.path.abspath(dbgpath), *splitted_name)
            if os.path.exists(patchpath):
                #print("pkg_dir found:", patchpath)
                break
            elif os.path.exists(patchpath+'.py'):
                #print("patchpyfilefound", patchpath+'.py')
                patchfilename = patchpath+'.py'
                break
            elif os.path.exists(patchpath+".pyc"):
                #print("TODO compiled file found", patchpath+".pyc")
                break
            else:
                pass
        else:
            #print("No patch file found")
            return # use standard import mechanism if no patch module exists
        if self.debugger:
            self.debugger.add_skip_module(fullname)
        
        if subname != fullname and self.path is None:
            #print("subname!=fullname and path is none")
            #print("fullname", fullname, path, self.path)
            try:
                file, filename, stuff = imp.find_module(subname, path)
            except ImportError:
                #print("Import Error for submodule")
                return None
            
            return EpdbImportLoader(file, filename, stuff,
                            patchfilename=patchfilename, debugger=self.debugger)
        if self.path is None:
            path = None
        else:
            path = [self.path]
        try:
            #print("imp.find_module", subname, path)
            file, filename, stuff = imp.find_module(subname, path)
        except ImportError:
            #print("Import Error")
            return None
        #print("Return Loader")
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
        #print("[Load] ", fullname, self.filename, self.stuff)
                    
        mod = imp.load_module(fullname, self.file, self.filename, self.stuff)
        if self.file:
            self.file.close()
        mod.__loader__ = self  # for introspection
        #print(mod.__dict__.keys())
        #print("Loadpath: ", getattr(mod, '__path__', None), fullname)
        if self.patchfilename:
            #print("Patch module", fullname)
            with open(self.patchfilename) as patchfile:
                exec(patchfile.read(), mod.__dict__)
        return mod