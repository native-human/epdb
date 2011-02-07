#!/usr/bin/python3
import pdb
import sys
import linecache
import cmd
import bdb
from reprlib import Repr
import os
import os.path
import re
import pprint
import traceback
import snapshotting
import builtins
import types
import _thread
import configparser
import shareddict
import tempfile
import resources
import time
import asyncmd
import io
import socket
from debug import debug
#from debug import sendcmd
from reprlib import Repr
import string

dbgpath = None

_repr = Repr()
_repr.maxstring = 200
_saferepr = _repr.repr

line_prefix = '\n-> '

def readconfig():
    global dbgpath
    sys.path = origpath
    try:
        config = configparser.ConfigParser()
        config.read(os.path.expanduser("~/.config/epdb.conf"))
        dbgmods = config.get('Main', 'dbgmods')
    except:
        pass
    dbgpath = dbgmods
    #debug("dbgmods", dbgmods)
    if not dbgmods in sys.path:
        sys.path.append(dbgmods)

origpath = sys.path[:]
readconfig()

#debug("PATH: ", sys.path)

import dbg

__pythonimport__ = builtins.__import__

__all__ = ["run", "pm", "Epdb", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

mode = 'normal'

def __bltins_import__(name, globals=None, locals=None, fromlist=None, level=-1):
    mod = __pythonimport__(name, globals, locals, fromlist, level)
    try:
        module = __pythonimport__('__builtins', globals, locals, fromlist)
    except ImportError:
        pass
        #debug("Failed importing __builtins", sys.path)
    else:
        #debug('Importing __builtins with patching', name, module.__dict__.keys())
        for key in module.__dict__.keys():
            if key == name:
                continue
            if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
                continue
            
            # if the name doesn't exist in the original file -> ignore it
            try:
                setattr(mod, '__orig__'+key, getattr(mod,key))
                setattr(mod, key, getattr(module, key))
            except AttributeError:
                pass
    return mod


def __import__(name, globals=None, locals=None, fromlist=None, level=-1):
    if os.path.basename(sys._current_frames()[_thread.get_ident()].f_back.f_code.co_filename) in ['epdb.py', 'snaphotting.py', 'dbg.py', 'shareddict.py', 'debug.py', 'bdb.py', "cmd.py", "fnmatch.py"]:
        return __pythonimport__(name, globals, locals, fromlist, level)
    else:
        pass
    new = True
    if name in dbg.modules:
        new = False
    mod = __pythonimport__(name, globals, locals, fromlist, level)
    if new:
        dbg.modules.append(name)
        if name[:2] != '__':
            try:
                #debug("try import  __", name, sep="")
                module = __pythonimport__('__'+name, globals, locals, fromlist)
                #debug("success")
            except ImportError:
                pass
                #debug("nosuccess", sys.path)
                #debug("nosuccess", name)
            else:
                debug('Importing a module with patching', name)
                for key in module.__dict__.keys():
                    #if key == name:
                    #    continue
                    if key in ['__builtins__', '__file__', '__package__', '__name__', '__doc__', 'dbg']:
                        continue
                    
                    # if the name doesn't exist in the original file -> ignore it
                    try:
                        setattr(mod, '__orig__'+key, getattr(mod,key))
                        setattr(mod, key, getattr(module, key))
                    except AttributeError:
                        pass
    return mod

class EpdbExit(Exception):
    """Causes a debugger to be exited for the debugged python process."""
    pass

class EpdbPostMortem(Exception):
    """Raised when the program finishes and enters a interactive shell"""
    pass

class SnapshotData:
    def __init__(self, id, ic):
        self.id = id
        self.ic = ic
        self.references = 0

class UdsDbgCom():
    def __init__(self, debugger, filename):
        self.debugger = debugger
        self.prompt = '(Epdb) \n'
        self.aliases = {}
        self.filename = filename
        
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(filename)
        self.cmdqueue = []
        self.identchars = string.ascii_letters + string.digits + '_'
        
    def do_p(self, arg):
        return self.debugger.cmd_print(arg)
    do_print = do_p

    def do_set_resources(self, args):
        return self.debugger.cmd_set_resources(arg)
        
    def do_snapshot(self, arg, temporary=0):
        return self.debugger.cmd_snapshot(arg, temporary)

    def do_restore(self, arg):
        return self.debugger.cmd_restore(arg)

    def do_continued(self, arg):
        return self.debugger.cmd_continued(arg)
    
    def do_nde(self, arg):
        """Shows the current nde. Debugging only."""
        return self.debugger.cmd_nde(arg)

    def do_resources(self, arg):
        return self.debugger.cmd_resources(arg)

    def do_ic(self, arg):
        """Shows the current instruction count"""
        return self.debugger.cmd_ic(arg)
        
    def do_timelines(self, arg):
        """List all timelines."""
        return self.debugger.cmd_timelines(arg)
    
    def do_timeline_snapshots(self, arg):
        "List all snapshots for the timeline"
        return self.debugger.cmd_timeline_snapshots(arg)

    def do_switch_timeline(self, arg):
        """Switch to another timeline"""
        return self.debugger.cmd_switch_timeline(arg)
        
    def do_current_timeline(self, arg):
        """View the name of the current timeline"""
        return self.debugger.cmd_current_timeline(arg)

    def do_newtimeline(self, arg):
        """Create a new timeline. This allows changing the program flow from the last run"""
        return self.debugger.cmd_newtimeline(arg)

    
    def do_EOF(self, arg):
        """Quit the program, if connection terminates"""
        return self.debugger.cmd_quit()

    def do_quit(self, arg):
        """quits the program"""
        return self.debugger.cmd_quit()
    
    def do_mode(self, arg):
        """Shows the current mode."""
        return self.debugger.cmd_mode(arg)
    
    def do_ron(self, arg):
        """Enables reversible debugging"""
        return self.debugger.cmd_ron(arg)
    
    def do_roff(self, arg):
        """Disables reversible debugging"""
        return self.debugger.cmd_roff(arg)
        
    def do_rstep(self, arg):
        """Steps one step backwards"""
        return self.debugger.cmd_rstep(arg)
        
    def do_rnext(self, arg):
        """Reverse a next command."""
        return self.debugger.cmd_rnext(arg)
        
    def do_rcontinue(self, arg):
        """Continues in backward direction"""
        return self.debugger.cmd_rcontinue(arg)

    def do_step(self, arg):
        return self.debugger.cmd_step(arg)
    do_s = do_step    

    def do_next(self, arg):
        return self.debugger.cmd_next(arg)
    do_n = do_next
    
    def do_continue(self, arg):
        return self.debugger.cmd_continue(arg)
    do_c = do_cont = do_continue
        
    def do_return(self, arg):
        "not implmented yet for epdb"
    #do_r = do_return   

    def do_activate_snapshot(self, arg):
        """activate a snapshot of the current timeline"""
        return self.debugger.cmd_activate_snapshot(arg)
        
    def do_show_break(self, arg):
        return self.debugger.cmd_show_break(arg)
    
    def do_break(self, arg, temporary = 0):
        return self.debugger.cmd_break(arg, temporary)
    
    def do_clear(self, arg):
        """Three possibilities, tried in this order:
        clear -> clear all breaks, ask for confirmation
        clear file:lineno -> clear all breaks at file:lineno
        clear bpno bpno ... -> clear breakpoints by number"""
        return self.debugger.cmd_clear(arg)
   
    do_cl = do_clear # 'c' is already an abbreviation for 'continue'
   
    def do_commands(self, arg):
        """Not supported yet"""
        # because epdbs implementation calls the blocking cmdloop there

    def preloop(self):
        self.debugger.preprompt()

    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        This may be overridden, but should not normally need to be;
        see the precmd() and postcmd() methods for useful execution hooks.
        The return value is a flag indicating whether interpretation of
        commands by the interpreter should stop.

        """
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if cmd == '':
            return self.default(line)
        else:
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                return self.default(line)
            return func(arg)

    def parseline(self, line):
        """Parse the line into a command name and a string containing
        the arguments.  Returns a tuple containing (command, args, line).
        'command' and 'args' may be None if the line couldn't be parsed.
        """
        line = line.strip()
        if not line:
            return None, None, line
        elif line[0] == '?':
            line = 'help ' + line[1:]
        elif line[0] == '!':
            if hasattr(self, 'do_shell'):
                line = 'shell ' + line[1:]
            else:
                return None, None, line
        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i = i+1
        cmd, arg = line[:i], line[i:].strip()
        return cmd, arg, line

    def send(self, line):
        bline = line.encode("UTF-8")
        try:
            if bline.endswith(b"\r\n"):
                self.sock.send(bline)
            elif bline.endswith(b"\n") or bline.endswith(b"\r"):
                self.sock.send(bline[:-1]+b"\r\n")
            else:
                self.sock.send(bline+b"\r\n")
        except socket.error:
            print("socket.error")
            self.onecmd('quit')
        

    def get_cmd(self):
        self.preloop()
        stop = None
        line = b''
        while not stop:
            try:
                #line = input(self.prompt)
                while not b"\r\n" in line:
                    got = self.sock.recv(4096)
                    line += got
                    if line == b'':
                        line = b'EOF'
                        break
                    elif got == b'':
                        break
            except EOFError:
                line = 'EOF'

            firstline,_,line = line.partition(b"\r\n")
            firstline = firstline.decode("UTF-8")
            firstline = firstline.rstrip('\r\n')
            print("Received Line:", firstline)
            #line = self.precmd(line)
            stop = self.onecmd(firstline)
            #stop = self.postcmd(stop, line)
        #self.postloop()

  
    def send_ic_mode(self, ic, mode):
        self.send("ic#" + str(ic) + "\r\n")
        self.send("mode#" + mode + "\r\n")

    def send_time(self, time=None):
        if time is None:
            self.send("time#" + "\r\n")
        else:
            self.send("time#" + str(time) + "\r\n")
 
    def send_var(self, varname, value):
        self.send("var#" + varname + "#" + value + '\r\n')
   
    def send_varerr(self, varname):
        self.send("varerror#"+ varname + "\r\n")
    
    def send_synterr(self, file, ic):
        self.send("syntax_error#"+ file + "#" + ic + "\r\n")
    
    def send_lastline(self, line):
        self.send("lineinfo#" + line+"\r\n")
        
    def send_resources(self, resources):
        # resources [(resource_type, resource_location, [(id, ic), ...]), ...]
        self.send("list resources#\r\n")
        for rtype, rloc, rlist in resources:
            self.send('resource#' + rtype + '#' + rloc + '\r\n')
            for rid, ric in rlist:
                self.send('resource_entry#' + rtype + '#' + rloc + '#' + str(rid) + '#' + str(ric) + '\r\n')
           
    def send_timeline_snapshots(self, snapshot_list):
        self.send("list_timeline_snapshots#\r\n")
        for snapshot in snapshot_list:
            self.send('tsnapshot#' + str(snapshot.id) + '#' + str(snapshot.ic) + "\r\n")
    
    def send_timeline_switched(self, timeline_name):
        self.send("switched to timeline#", timeline_name + "\r\n")
         
    def send_newtimeline_success(self, name):
        self.send("newtimeline successful#"+name+"\r\n")
           
    def send_file_pos(self, formatted_line):
        self.send('lineinfo#' + formatted_line + '\r\n')
    
    def send_expect_input(self):
        self.send("expect input#\r\n")
        
    def send_stdout(self, stdout):
        self.send("clear_stdout#\r\n")
        lines = stdout.splitlines()
        for line in stdout:
            self.send("add_stdout_line#"+'\r\n')
    
    def send_break_nosuccess(self, filename, lineno, reason):
        self.send("break nosuccess#" + str(filename) + "#" + str(lineno) + \
                  "#" + str(reason)+ "\r\n")
    
    def send_break_success(self, number, filename, lineno):
        self.send("break success#" + str(number) + "#" + str(filename) + \
                  "#" + str(lineno)+ "\r\n")
        
    def send_clear_success(self, number):
        self.send("clear success#" + str(number)+ "\r\n")

class StdDbgCom(cmd.Cmd):
    def __init__(self, debugger):
        asyncmd.Asyncmd.__init__(self)
        self.debugger = debugger
        self.prompt = '(Epdb) \n'
        self.aliases = {}
        
    def do_p(self, arg):
        return self.debugger.cmd_print(arg)
    do_print = do_p

    def do_set_resources(self, args):
        return self.debugger.cmd_set_resources(arg)
        
    def do_snapshot(self, arg, temporary=0):
        return self.debugger.cmd_snapshot(arg, temporary)

    def do_restore(self, arg):
        return self.debugger.cmd_restore(arg)

    def do_continued(self, arg):
        return self.debugger.cmd_continued(arg)
    
    def do_nde(self, arg):
        """Shows the current nde. Debugging only."""
        return self.debugger.cmd_nde(arg)

    def do_resources(self, arg):
        return self.debugger.cmd_resources(arg)

    def do_ic(self, arg):
        """Shows the current instruction count"""
        return self.debugger.cmd_ic(arg)
        
    def do_timelines(self, arg):
        """List all timelines."""
        return self.debugger.cmd_timelines(arg)
    
    def do_timeline_snapshots(self, arg):
        "List all snapshots for the timeline"
        return self.debugger.cmd_timeline_snapshots(arg)

    def do_switch_timeline(self, arg):
        """Switch to another timeline"""
        return self.debugger.cmd_switch_timeline(arg)
        
    def do_current_timeline(self, arg):
        """View the name of the current timeline"""
        return self.debugger.cmd_current_timeline(arg)

    def do_newtimeline(self, arg):
        """Create a new timeline. This allows changing the program flow from the last run"""
        return self.debugger.cmd_newtimeline(arg)

    def do_quit(self, arg):
        """quits the program"""
        return self.debugger.cmd_quit()
    
    def do_mode(self, arg):
        """Shows the current mode."""
        return self.debugger.cmd_mode(arg)
    
    def do_ron(self, arg):
        """Enables reversible debugging"""
        return self.debugger.cmd_ron(arg)
    
    def do_roff(self, arg):
        """Disables reversible debugging"""
        return self.debugger.cmd_roff(arg)
        
    def do_rstep(self, arg):
        """Steps one step backwards"""
        return self.debugger.cmd_rstep(arg)
        
    def do_rnext(self, arg):
        """Reverse a next command."""
        return self.debugger.cmd_rnext(arg)
        
    def do_rcontinue(self, arg):
        """Continues in backward direction"""
        return self.debugger.cmd_rcontinue(arg)

    def do_step(self, arg):
        return self.debugger.cmd_step(arg)
    do_s = do_step    

    def do_next(self, arg):
        return self.debugger.cmd_next(arg)
    do_n = do_next
    
    def do_continue(self, arg):
        return self.debugger.cmd_continue(arg)
    do_c = do_cont = do_continue
        
    def do_return(self, arg):
        "not implmented yet for epdb"
    #do_r = do_return   

    def do_activate_snapshot(self, arg):
        """activate a snapshot of the current timeline"""
        return self.debugger.cmd_activate_snapshot(arg)
        
    def do_show_break(self, arg):
        return self.debugger.cmd_show_break(arg)
    
    def do_break(self, arg, temporary = 0):
        return self.debugger.cmd_break(arg, temporary)
    
    def do_clear(self, arg):
        """Three possibilities, tried in this order:
        clear -> clear all breaks, ask for confirmation
        clear file:lineno -> clear all breaks at file:lineno
        clear bpno bpno ... -> clear breakpoints by number"""
        return self.debugger.cmd_clear(arg)
   
    do_cl = do_clear # 'c' is already an abbreviation for 'continue'
   
    def do_commands(self, arg):
        """Not supported yet"""
        # because epdbs implementation calls the blocking cmdloop there

    def precmd(self, line):
        """Handle alias expansion and ';;' separator."""
        if not line.strip():
            return line
        args = line.split()
        while args[0] in self.aliases:
            line = self.aliases[args[0]]
            ii = 1
            for tmpArg in args[1:]:
                line = line.replace("%" + str(ii),
                                      tmpArg)
                ii = ii + 1
            line = line.replace("%*", ' '.join(args[1:]))
            args = line.split()
        # split into ';;' separated commands
        # unless it's an alias command
        if args[0] != 'alias':
            marker = line.find(';;')
            if marker >= 0:
                # queue up everything after marker
                next = line[marker+2:].lstrip()
                self.cmdqueue.append(next)
                line = line[:marker].rstrip()
        return line

    def preloop(self):
        self.debugger.preprompt()

    def get_cmd(self):
        self.cmdloop()
  
    def send_ic_mode(self, ic, mode):
        self.send_raw("ic:", ic, "mode:", mode)

    def send_time(self, time=None):
        if time is None:
            self.send_raw("time:")
        else:
            self.send_raw("time: ", time)
 
    def send_var(self, varname, value):
        self.send_raw("var#", varname, "#", value,'#', sep='')
   
    def send_varerr(self, varname):
        self.send_raw("varerror#", arg)
    
    def send_synterr(self, file, ic):
        self.send_raw("syntax_error", file, ic, '', sep='#')
    
    def send_lastline(self, line):
        self.send_raw("> " + line, prefix="")
        
    def send_resources(self, resources):
        # resources [(resource_type, resource_location, [(id, ic), ...]), ...]
        self.send_raw("show resources#")
        for rtype, rloc, rlist in resources:
            self.send_raw('resource#', rtype,'#', rloc,'#',sep='')
            for rid, ric in rlist:
                self.send_raw('resource_entry#', rtype,'#', rloc,'#',rid,'#', ric,'#', sep='')
           
    def send_timeline_snapshots(self, snapshot_list):
        self.send_raw("timeline_snapshots#")
        for snapshot in snapshot_list:
            self.send_raw('tsnapshot#', snapshot.id, '#', snapshot.ic,'#',sep='')
    
    def send_timeline_switched(self, timeline_name):
        self.send_raw("Switched to timeline", timeline_name)
         
    def send_newtimeline_success(self,name):
        self.send_raw("newtimeline successful")
           
    def send_file_pos(self, formatted_line):
        self.send_raw('>', formatted_line, prefix='')
    
    def send_expect_input(self):
        self.send_raw("expect input#")
        
    def send_stdout(self, stdout):
        self.send_raw("-->")
        self.send_raw(stdout, prefix="#->", end='')
        
    def send_raw(self, value, *args, sep=' ', end='\n', prefix="#"):
        output = io.StringIO()
        print(value, *args, sep=sep, end=end, file=output)
        for line in output.getvalue().splitlines():
            print(prefix + line)
    
class Epdb(pdb.Pdb):
    def __init__(self, uds_file=None):
        pdb.Pdb.__init__(self, skip=['random', 'time', 'debug', 'fnmatch', 'epdb',
                'posixpath', 'shareddict', 'pickle', 'os', 'dbg', 'locale',
                'codecs', 'types', 'io', 'builtins', 'ctypes', 'linecache',
                'uuid', 'shelve', 'collections', 'tempfile', '_thread',
                'subprocess', 're', 'sre_parse', 'struct', 'ctypes',
                'threading', 'ctypes._endian', 'copyreg', 'ctypes.util',
                'sre_compile', 'abc', '_weakrefset', 'base64', 'dbm',
                'traceback', 'tokenize', 'dbm.gnu', 'dbm.ndbm', 'dbm.dumb',
                'functools', 'resources', 'bdb', 'debug', 'runpy'])
        #asyncmd.Asyncmd.__init__(self)
        if uds_file:
            dbg.dbgcom = self.dbgcom = UdsDbgCom(self, uds_file)
        else:
            dbg.dbgcom = self.dbgcom = StdDbgCom(self)
        
        self.init_reversible()
    
    def is_skipped_module(self, module_name):
        """Extend to skip all modules that start with double underscore"""
        base = pdb.Pdb.is_skipped_module(self, module_name)
        if base == True:
            return True
        #debug("not skipped", module_name)
        if module_name == '__main__':
            return False
        return module_name.startswith('__')
    
    def findsnapshot(self, ic):
        """Looks for a snpashot to use for stepping backwards.
        Returns snapshot data"""
        bestic = -1
        bestsnapshot = None
        snapshots = dbg.current_timeline.get_snapshots()
        for sid in snapshots:
            e = self.snapshots[sid]
            if e.ic <= ic:
                if e.ic > bestic:
                    bestic = e.ic
                    bestsnapshot = e
        return bestsnapshot
        
    def findnextbreakpointic(self):
        """Looks for the next ic that has a breakpoint. It only looks at executed
        instruction counts. Returns -1 if nothing was found"""
        continued = dbg.current_timeline.get_continue()
        from breakpoint import Breakpoint
        bestic = -1
        for bp in Breakpoint.bplist:
            #debug("Checking Bp: ", bp)
            try:
                for bpic in continued[bp]:
                    #debug("Try bpic", bpic)
                    if bpic > dbg.ic:
                        break
                else:
                    continue
                if bestic == -1:
                    bestic = bpic
                else:
                    bestic = min(bestic, bpic)
            except KeyError:
                pass
        return bestic
    
    def findprecedingbreakpointic(self):
        """Looks for a preceding ic that has a breakpoint. It only looks at executed
        instruction counts. Returns 0 if nothing was found"""
        continued = dbg.current_timeline.get_continue()
        from breakpoint import Breakpoint
        bestic = 0
        for bp in Breakpoint.bplist:
            #debug("Checking Bp: ", bp)
            try:
                for bpic in reversed(continued[bp]):
                    #debug("Try bpic")
                    if bpic < dbg.ic:
                        break
                else:
                    continue
                if bestic == -1:
                    bestic = bpic
                else:
                    bestic = max(bestic, bpic)
            except KeyError:
                pass
        return bestic
    
    def make_snapshot(self):
        # TODO make snapshot in roff and ron mode
        #fdebug("make snapshot", dbg.ic, self.snapshot_id)
        snapshot = snapshotting.Snapshot(dbg.ic, self.snapshot_id)
        self.psnapshot = self.snapshot
        self.psnapshot_id = self.snapshot_id
        self.pss_ic = self.ss_ic
        self.snapshot = snapshot
        self.snapshot_id = snapshot.id
        # self.ss_ic = self.ic
        self.ss_ic = dbg.ic
        
        snapshotdata = SnapshotData(id=self.snapshot_id, ic=dbg.ic)
        self.snapshots[snapshotdata.id] = snapshotdata
        
        if not snapshot.activated:
            dbg.current_timeline.add(snapshotdata.id)
        if snapshot.activation_type == "step_forward":
            # debug("step forward activation", snapshot.step_forward, dbg.ic)
            self.stopnocalls = None
            self.running_mode = "stopafter"
            if snapshot.step_forward > 0:
                dbg.mode = 'replay'
                self.stopafter = snapshot.step_forward
                #debug("stopafter", self.stopafter)
                return 1
            else:
                if dbg.ic == dbg.current_timeline.get_max_ic():
                    dbg.mode = 'normal'
                else:
                    dbg.mode = 'redo'
                #debug("SET MODE TO: ", dbg.mode)
                return
        elif snapshot.activation_type == "stopatnocalls":
            #debug("STOPATNOCALLS", snapshot.nocalls)
            self.set_next(self.curframe)
            #self.set_step()
            self.stopnocalls = snapshot.nocalls
            self.running_mode = 'next'
            return 1
        elif snapshot.activation_type == "continue":
            #debug("Continue activation", dbg.ic)
            self.set_continue()
            #self.set_step()
            self.running_mode = 'continue'
            dbg.mode = "redo"
            return 1
        else:
            # This typically happens if the snapshot is made
            return 'snapshotmade'

    def preprompt(self):
        t = time.time()
        self.dbgcom.send_ic_mode(dbg.ic, dbg.mode)
        if self.command_running_start_time:
            self.dbgcom.send_time(t-self.command_running_start_time)
        else:
            self.dbgcom.send_time()
        self.command_running_start_time = None
    
    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        import __main__
        __main__.__dict__.clear()
        bltins = __bltins_import__("builtins").__dict__
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": bltins,
                                })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = 0
        globals = __main__.__dict__
        #locals = globals
        #debug("##################",dbgpath)
        sys.path.append('/home/patrick/myprogs/epdb/dbgmods')

        with open(filename, "rb") as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)
        builtins.__import__ = __import__            
        
        self.run(statement)
        
        dbg.ic += 1
        if self._user_requested_quit:
            return
        debug("Program has finished")
        #debug("Going into post-mortem interaction mode", dbg.ic)
        dbg.mode = "post_mortem"
        self.set_resources()
        self.is_postmortem=True
        #self.cmdloop()
        self.interaction(self.lastframe, None)
        
    def init_reversible(self):
        #self.command_run
        ning_start_time = time.time()
        self.command_running_start_time = None
        #debug('Init reversible')
        dbg.tempdir = tempfile.mkdtemp()
        self.mp = snapshotting.MainProcess()
        from breakpoint import Breakpoint
        #self.ic = 0             # Instruction Counter
        self.ron = True
        
        dbg.ic = 0
        
        self.ss_ic = 0
        self.snapshot = None
        self.snapshot_id = None
        
        self.pss_ic = 0
        self.psnapshot = None
        self.psnapshot_id = None
        
        self.running_mode = None
        self.stopafter = -1
        
        self.stopnocalls = None
        self.nocalls = 0
        
        # The call_stack contains ic for every call in a previous frame
        # This is used in user_return to find its corresponding call
        self.call_stack = []
        
        self.rnext_ic = {}    
        #self.rcontinue_ln = {}
        
        # steps from last snapshot
        self.stepsfromlastss = None
        
        self.is_postmortem = False
        
        self.starttime = None
        self.runningtime = 0
        
        self.breaks = shareddict.DictProxy('breaks')
        self.snapshots = shareddict.DictProxy('snapshots')
        
        dbg.current_timeline.new_resource('__stdout__', '')
        dbg.stdout_resource_manager = resources.StdoutResourceManager()
        dbg.current_timeline.create_manager(('__stdout__', ''), dbg.stdout_resource_manager)
        self.stdout_manager = dbg.current_timeline.get_manager(('__stdout__',''))
        id = self.stdout_manager.save()
        dbg.current_timeline.get_resource('__stdout__', '')[dbg.ic] = id
    
    def trace_dispatch(self, frame, event, arg):
        # debug("trace_dispatch")
        return pdb.Pdb.trace_dispatch(self, frame, event, arg)
    
    def set_resources(self):
        """Sets the resources for the actual position"""
        debug("set resources")
        #debug("r: ", dbg.current_timeline.get_resources())
        for k in dbg.current_timeline.get_resources():
            resource = dbg.current_timeline.get_resource(*k)
            for i in range(dbg.ic, -1, -1):
                res = resource.get(i, None)
                if not res is None:
                    break
            else:
                for i in range(dbg.ic+1, dbg.current_timeline.get_max_ic()):
                    res = resource.get(i, None)
                    if not res is None:
                        break
                    else:
                        debug("Error: No key found for set resources")
                        return
            #debug("Key {0} for resource {1}".format(res, resource))
            #debug("k: ", k)
            manager = dbg.current_timeline.get_manager(k)
            #debug("manager: ", manager)
            manager.restore(res)
            #for rk in resource:
            #    debug(" ", rk, resource[rk])
            #debug(k)
            
    def cmd_print(self, arg):
        try:
            self.dbgcom.send_var(arg, repr(self._getval(arg)))
        except:
            self.dbgcom.send_varerr(arg)
    # make "print" an alias of "p" since print isn't a Python statement anymore
            
    def cmd_set_resources(self, args):
        self.set_resources()
    
    def user_exception(self, frame, exc_info):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        exc_type, exc_value, exc_traceback = exc_info
        frame.f_locals['__exception__'] = exc_type, exc_value
        exc_type_name = exc_type.__name__
        print(exc_type_name + ':', _saferepr(exc_value), file=self.stdout)
        if exc_type == SyntaxError:
            self.dbgcom.send_synterr(exc_value[1][0], exc_value[1][1])
        self.interaction(frame, exc_traceback)
    
    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if hasattr(self, 'lastframe'):
            del self.lastframe
        self.lastframe = frame
        #debug('lastframe', self.lastframe.f_globals.get('__name__'))
        
        actualtime = time.time()
        if self.starttime:
            self.runningtime += actualtime - self.starttime
        #debug("user_line", frame.f_code.co_filename, self.starttime, time.time())
        dbg.ic += 1
        try:
            lineno=frame.f_lineno
        except:
            lineno="err"
        #debug("user line: ", dbg.ic, lineno)
        # TODO only make snapshots in normal mode?
        
        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno<= 0):
                return
            dbg.ic = 0
            r = self.make_snapshot()
            self._wait_for_mainpyfile = 0
            if r == 'snapshotmade':
                #debug("snapshotmade")
                self.interaction(frame, None)
                return
            else:
                pass
                #debug("main snapshot activated")
        
        if dbg.snapshottingcontrol.get_make_snapshot():
            r = self.make_snapshot()
            #debug('interaction snapshot made or activated', r)
            dbg.snapshottingcontrol.clear_make_snapshot()
            self.runningtime = 0
        elif self.runningtime >= 1 and dbg.mode == 'normal':
            #debug("Make snapshot because of running time")
            r = self.make_snapshot()
            self.runningtime = 0
            
        self.lastline = "{filename}({lineno})<module>()".format(filename=frame.f_code.co_filename, lineno=frame.f_lineno)
        def setmode():
            #debug("setmode: ", dbg.ic, dbg.current_timeline.get_max_ic())
            if dbg.mode == 'redo':
                if dbg.ic >= dbg.current_timeline.get_max_ic():
                    dbg.mode = 'normal'
                    self.set_resources()

        lineno = frame.f_lineno
        filename = frame.f_code.co_filename
        filename = self.canonic(filename)
        
        if dbg.mode == 'normal':
            continued = dbg.current_timeline.get_continue()
            try:
                l = continued[(filename,lineno)]
                l.append(dbg.ic)
                continued[(filename, lineno)] = l
            except:
                continued[(filename, lineno)] = [dbg.ic]
                
        if self.running_mode == 'continue':
            #debug("running mode continue")
            if dbg.mode == 'redo':
                setmode()
            if dbg.mode == 'normal':
                if self.break_here(frame):
                    setmode()
                    #debug("user_line interaction")
                    self.interaction(frame, None)
        elif self.running_mode == 'next':
            setmode()
            if self.break_here(frame):
                self.stopnocalls = None
                #debug("user_line interaction")
                self.set_resources()
                self.interaction(frame, None)
            elif self.stopnocalls and self.nocalls <= self.stopnocalls:
                #setmode()
                #debug("user_line interaction")
                self.set_resources()
                self.interaction(frame, None)
        elif self.running_mode == 'step':
            setmode()
            self.set_resources()
            self.interaction(frame, None)
        elif self.running_mode == 'stopafter':
            #debug("STOPAFTER USERLINE", "stopafter:", self.stopafter, "ic", dbg.ic)
            if self.stopafter <= 0:
                if dbg.current_timeline.get_max_ic() > dbg.ic:
                    dbg.mode = 'redo'
                else:
                    dbg.mode = 'normal'
                #debug("stopafteruserline interaction")
                self.set_resources()
                self.interaction(frame, None)
            else:
                self.stopafter -= 1
                setmode()
        else:
            #debug("running mode else")
            self.interaction(frame, None)
        self.starttime = time.time()
        
    def user_call(self, frame, argument_list):
        #debug("user_call")
        self.call_stack.append(dbg.ic)
        nextd = dbg.current_timeline.get_next()
        self.nocalls += 1
        if not dbg.ic in nextd:
            nextd[dbg.ic] = None
        if dbg.mode == 'replay':
            pass
        elif self.running_mode == 'continue':
            pass
        elif self.running_mode == 'next':
            #self.nocalls += 1
            pass
        elif self.running_mode == 'step':
            pass
        else:
            if self._wait_for_mainpyfile:
                return
            debug('Calling usercall interaction', self.running_mode, dbg.mode, self.stopafter)
            self.interaction(frame, None)
    
    def stop_here(self, frame):
        if pdb.Pdb.stop_here(self, frame):
            return True
        return False

    def set_continue(self):
        if not self.ron:
            return pdb.Pdb.set_continue(self)
        # Debugger overhead needed to count instructions
        self.set_step()
        self.running_mode = 'continue'

    def cmd_snapshot(self, arg, temporary=0):
        """snapshot - makes a snapshot"""
        ic = dbg.ic
        #debug("Ic:", ic)
        snapshots = dbg.current_timeline.get_snapshots()
        for sid in snapshots:
            s = self.snapshots[sid]
            if ic == s.ic:
                debug("This ic already has an instruction count")
                return
            
        r = self.make_snapshot()
        #debug("Ic after:", ic)
        #debug("self.stopafter:", self.stopafter)
        #debug("make return:", r)
        #debug("self.running mode", self.running_mode)
        if self.stopafter > 0:
            self.stopafter -= 1
        if r == "snapshotmade":
            self.dbgcom.send_lastline(self.lastline)
            return

        # TODO: support other running_modes
        # Note: This works for some reason for the other modes. However,
        # I am not sure if it works in every case (e.g.: if some other command
        # sets a different mode than set_step)
        if self.running_mode == 'stopafter' and self.stopafter == -1:
            self.preprompt()
            self.dbgcom.send_lastline(self.lastline)
            self.running_mode = None
            self.set_resources()
        return r
    
    def cmd_restore(self, arg):
        """Restore a previous Snapshot, e.g. restore 0"""
        # TODO leave current timeline and go into roff mode
        try:
            id = int(arg)
        except:
             debug('You need to supply an index, e.g. restore 0')
             return
            
        self.mp.activatesp(id)
        raise EpdbExit()
    
    def cmd_continued(self, arg):
        continued = dbg.current_timeline.get_continue()
        debug('continued: ', continued)
    
    def cmd_nde(self, arg):
        """Shows the current nde. Debugging only."""
        debug('nde:', dbg.nde)

    def cmd_resources(self, arg):
        l = []
        for k in dbg.current_timeline.get_resources():
            resource = dbg.current_timeline.get_resource(*k)
            #for rk in resource:
            #    debug(" ", rk, resource[rk])
            #debug("Resource: ", resource)
            rl = []
            for rid in resource:
                rl.append((rid, resource[rid]))
            l.append((k[0],k[1], rl))
        self.dbgcom.send_resources(l)
                #type, location, id, ic

    def cmd_ic(self, arg):
        """Shows the current instruction count"""
        debug('The instruction count is:', dbg.ic)
        
    def cmd_timelines(self, arg):
        """List all timelines."""
        dbg.timelines.show()
    
    def cmd_timeline_snapshots(self, arg):
        "List all snapshots for the timeline"
        snapshots = dbg.current_timeline.get_snapshots()
        l = []
        for sid in snapshots:
            e = self.snapshots[sid]
            l.append(e)
        self.dbgcom.send_timeline_snapshots(l)
    
    def cmd_switch_timeline(self, arg):
        """Switch to another timeline"""
        try:
            timeline = dbg.timelines.get(arg)
        except:
            debug("Timeline '",arg,"' doesn't exist", sep='')
            return    
        dbg.current_timeline.deactivate(dbg.ic)
        ic = timeline.get_ic()

        dbg.timelines.set_current_timeline(timeline.get_name())
        self.dbgcom.send_timeline_switched(timeline.get_name())
        dbg.current_timeline = timeline
        s = self.findsnapshot(ic)
        self.mp.activatesp(s.id, ic - s.ic)
        raise EpdbExit()
        
    def cmd_current_timeline(self, arg):
        """View the name of the current timeline"""
        dbg.current_timeline.show()
        
    def cmd_newtimeline(self, arg):
        """Create a new timeline. This allows changing the program flow from the last run"""
        if arg.strip() == '':
            debug("You need to supply a name for the new timeline")
            return
        newtimeline = dbg.current_timeline.copy(arg.strip(), dbg.ic)
        dbg.current_timeline.deactivate(dbg.ic)
        #dbg.ic = newtimeline.get_ic() # not necessary here because it is the same as in the previous one
        dbg.nde = newtimeline.get_nde()
        dbg.timelines.set_current_timeline(newtimeline.get_name())
        dbg.current_timeline = newtimeline
        dbg.mode = 'normal'
        self.dbgcom.send_ic_mode(dbg.ic, dbg.mode)
        self.dbgcom.send_newtimeline_success(arg.strip())
        
    def cmd_quit(self):
        self._user_requested_quit = 1
        self.mp.quit()
        self.set_quit()
        return 1
    
    def cmd_mode(self, arg):
        """Shows the current mode."""
        if self.is_postmortem:
            debug("mode: postmortem", dbg.mode)
        else:
            debug("mode: ", dbg.mode)
        
    def cmd_ron(self, arg):
        """Enables reversible debugging"""
        # TODO create or activate a new timeline
        self.ron = True
    
    def cmd_roff(self, arg):
        """Disables reversible debugging"""
        if self.ron:
            if dbg.ic > dbg.max_ic:
                dbg.max_ic = dbg.ic
            self.ron = False
            dbg.current_timeline.deactivate(dbg.ic)
    #
    #def interaction(self, frame, traceback):
    #    # Set all the resources before doing interaction
    #    self.running_mode = None
    #    self.set_resources()
    #    return pdb.Pdb.interaction(self, frame, traceback)
    
    def cmd_rstep(self, arg):
        """Steps one step backwards"""
        
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
        
        if dbg.ic > dbg.current_timeline.get_max_ic():
            #debug("Set max ic: ", dbg.ic)
            dbg.current_timeline.set_max_ic(dbg.ic)
            #debug("current maxic ", dbg.current_timeline.get_max_ic())
        
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return
        
        actual_ic = dbg.ic
        
        s = self.findsnapshot(dbg.ic-1)
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        steps = dbg.ic - s.ic - 1
        debug('snapshot activation', 'id:', s.id, 'steps:', steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def cmd_rnext(self, arg):
        """Reverse a next command."""
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
        
        if dbg.mode == 'post_mortem':
            self.do_rstep(arg)
        
        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)
        
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return
        
        nextic = self.rnext_ic.get(dbg.ic, dbg.ic-1)
        bpic = self.findprecedingbreakpointic()
        nextic = max(nextic, bpic)
        #debug('old nextic', nextic)
        #nextic = dbg.current_timeline.get_rnext().get(dbg.ic, dbg.ic-1)
        #debug('new nextic', nextic)
        
        s = self.findsnapshot(nextic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return
        
        steps = nextic - s.ic
        #debug('snapshot activation', s.id, steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def cmd_rcontinue(self, arg):
        """Continues in backward direction"""
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return
            
        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)
            #debug("Set max ic: ", dbg.ic)
        if dbg.ic == 0:
            debug("At the beginning of the program. Can't step back")
            return

        highestic = self.findprecedingbreakpointic()
            
        #debug("Highest ic found: ", highestic)

        s = self.findsnapshot(highestic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return
            
        steps = highestic - s.ic
        #debug('snapshot activation', s.id, steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()
        
    def set_next(self, frame):
        """Stop on the next line in or below the given frame."""
        if not self.ron:
            
            return pdb.Pdb.set_next(self, frame)
        self.set_step()
        self.running_mode = 'next'
        #self.nocalls = 0 # Increased on call - decreased on return
        self.stopnocalls = self.nocalls
    
    def set_step(self):
        """Stop on the next line in or below the given frame."""
        self.stopnocalls = None
        return pdb.Pdb.set_step(self)
        
    def cmd_step(self, arg):
        if self.is_postmortem:
            debug("You are at the end of the program. You cant go forward.")
            return
        if not self.ron:
            return pdb.Pdb.do_step(self, arg)
        #debug("Stepping in mode: ", dbg.mode)
        if dbg.mode == 'redo':
            #debug("Stepping in redo mode")
            s = self.findsnapshot(dbg.ic+1)
            if s == None:
                debug("No snapshot made. Can't step back")
                return
            if s.ic <= dbg.ic:
                debug("No snapshot found to step forward to. Step forward normal way", dbg.ic, s.ic)
                self.set_step()
                self.running_mode = 'step'
                return 1
            else:
                #debug('snapshot activation', s.id, 0)
                self.mp.activatesp(s.id, 0)
                raise EpdbExit()
        else:
            self.set_step()
            self.running_mode = 'step'
            self.command_running_start_time = time.time()
            return 1

    def cmd_next(self, arg):
        if self.is_postmortem:
            debug("You are at the end of the program. You cant go forward.")
            return
        if dbg.mode == 'redo':
            #debug("Next in redo mode")
            nextd = dbg.current_timeline.get_next()
            #steps = nextd.get(dbg.ic, dbg.ic+1) - dbg-ic
            nextic = nextd.get(dbg.ic, "empty")
            bpic = self.findnextbreakpointic()
            
            if nextic == "empty":
                # There is no function call in the current line -> same as stepping
                #debug('Stepping next')
                s = self.findsnapshot(dbg.ic+1)
                nextic = dbg.ic + 1
            elif nextic is None and bpic == -1:
                # The next command has to switch to normal mode at some point
                # Use the highest available snapshot
                #debug("mode switch next")
                s = self.findsnapshot(dbg.current_timeline.get_max_ic())
                if s.ic <= dbg.ic:
                    #debug("No snapshot found to next forward to. Next forward normal way", dbg.ic, s.ic)
                    self.set_next(self.curframe)
                    #self.set_step()
                    self.running_mode = 'next'
                    return 1
                else:
                    #debug('snapshot next activation', s.id, self.nocalls)
                    self.mp.activatenext(s.id, self.nocalls)
                    raise EpdbExit()
            else:
                # The next ends in the current timeline and no mode switch is needed.
                if nextic is None:
                    nextic = bpic
                elif bpic == -1:
                    pass
                else:
                    nextic = min(nextic, bpic)
                #debug('next inside timeline')
                s = self.findsnapshot(nextic)
            
            #s = self.findsnapshot(dbg.ic+1)
            if s == None:
                debug("No snapshot made. This shouldn't be")
                return
            if s.ic <= dbg.ic:
                #debug("No snapshot found to next forward to. Next forward normal way", dbg.ic, s.ic)
                self.set_next(self.curframe)
                #self.set_step()
                self.running_mode = 'next'
                return 1
            else:
                #debug('snapshot activation', s.id, s.ic - nextic)
                self.mp.activatesp(s.id, s.ic - nextic)
                raise EpdbExit()            
        else:
            self.command_running_start_time = time.time()
            return pdb.Pdb.do_next(self, arg)
    do_n = cmd_next
    
    def cmd_continue(self, arg):
        if self.is_postmortem:
            debug("You are at the end of the program. You cant go forward.")
            return
        if dbg.mode == 'redo':
            #debug("Continue in redo mode")
            bestic = self.findnextbreakpointic()
            if bestic == -1:
                #debug("redo_cont: No future bp in executed instructions found")
                # go to the highest snapshot and continue
                s = self.findsnapshot(dbg.current_timeline.get_max_ic())
                #debug("current_ic", dbg.ic, "snapshot_ic", s.ic)
                if dbg.ic < s.ic:
                    #debug("activate continue")
                    self.mp.activatecontinue(s.id)
                    raise EpdbExit()
                else:
                    pass
                    #debug("normal continue")
            else:
                #debug("redo_cont: Breakpoint found", bestic)
                # find snapshot and continue
                s = self.findsnapshot(bestic)
                self.mp.activatesp(s.id, bestic - s.ic)
                raise EpdbExit()
        else:
            self.command_running_start_time = time.time()
        return pdb.Pdb.do_continue(self, arg)
        
    def cmd_return(self, arg):
        debug("Return not implemented yet for epdb")

    def set_quit(self):
        pdb.Pdb.set_quit(self)
    
    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        try:
            callic = self.call_stack.pop()
            self.rnext_ic[dbg.ic + 1] = callic
            #dbg.current_timeline.get_rnext()[dbg.ic + 1] = callic
            next_ic = dbg.current_timeline.get_next()
            next_ic[callic] = dbg.ic + 1
        except:
            # TODO this usually happens when the program has finished
            # or ron was set when there was something on the stack
            # in this case epdb simply fall back to step backwards.
            
            # In case the program ends send the information of the last line
            # executed.
            print("Error")
            self.dbgcom.send_lastline(self.lastline)
            #print(self.lastline)
            pass

        self.nocalls -= 1
        if dbg.mode == 'replay':
            pass
        elif  self.running_mode == 'continue':
            pass
        elif  self.running_mode == 'next':
            #self.nocalls -= 1
            pass
        elif  self.running_mode == 'step':
            pass
        else:
            frame.f_locals['__return__'] = return_value
            debug('--Return--')
            debug("user_return interaction")
            self.interaction(frame, None)
    
    def cmd_activate_snapshot(self, arg):
        """activate the snapshot with the given id"""

        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return

        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)

        actual_ic = dbg.ic
        snapshots = dbg.current_timeline.get_snapshots()
        for sid in snapshots:
            s = self.snapshots[sid]
            #print(repr(s.id), repr(arg))
            if s.id == int(arg):
                break
        else:
            debug("Snapshot not found in timeline")
            return

        steps = 0
        debug('snapshot activation', 'id:', s.id, 'steps:', steps)
        self.mp.activatesp(s.id, steps)
        raise EpdbExit()

    def dispatch_call(self, frame, arg):
        # XXX 'arg' is no longer used
        if self.botframe is None:
            # First call of dispatch since reset()
            self.botframe = frame.f_back # (CT) Note that this may also be None!
            return self.trace_dispatch
        
        #if not (self.stop_here(frame) or self.break_anywhere(frame)):
        if not self.stop_here(frame) and not self.break_anywhere(frame):
            # No need to trace this function
            return # None
        self.user_call(frame, arg)
        if self.quitting: raise BdbQuit
        return self.trace_dispatch
    
    # The following functions are the same as in bdp except for
    # The usage of the epdb Breakpoint implementation
    
    def break_anywhere(self, frame):
        # This check avoids many message calls
        if self.is_skipped_module(frame.f_globals.get('__name__')):
            return False
        return self.canonic(frame.f_code.co_filename) in self.breaks
    
    def break_here(self, frame):
        filename = self.canonic(frame.f_code.co_filename)
        if not filename in self.breaks:
            return False
        lineno = frame.f_lineno
        #debug("break_here", filename)
        if not lineno in self.breaks[filename]:
            # The line itself has no breakpoint, but maybe the line is the
            # first line of a function with breakpoint set by function name.
            lineno = frame.f_code.co_firstlineno
            if not lineno in self.breaks[filename]:
                return False

        # flag says ok to delete temp. bp
        (bp, flag) = effective(filename, lineno, frame)
        if bp:
            self.currentbp = bp.number
            if (flag and bp.temporary):
                self.do_clear(str(bp.number))
            return True
        else:
            return False
        
    def set_break(self, filename, lineno, temporary=0, cond = None,
                  funcname=None):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        import linecache # Import as late as possible
        line = linecache.getline(filename, lineno)
        if not line:
            #debug("END")
            return 'Line %s:%d does not exist' % (filename,
                                   lineno)
        if not filename in self.breaks:
            self.breaks[filename] = []
        list = self.breaks[filename]
        if not lineno in list:
            list.append(lineno)
            self.breaks[filename] = list  # This is necessary for the distributed application
        bp = Breakpoint(filename, lineno, temporary, cond, funcname)
        #debug('END')

    def clear_break(self, filename, lineno):
        from breakpoint import Breakpoint
        debug("Clear Break")
        filename = self.canonic(filename)
        if not filename in self.breaks:
            return 'There are no breakpoints in %s' % filename
        if lineno not in self.breaks[filename]:
            return 'There is no breakpoint at %s:%d' % (filename,
                                    lineno)
        # If there's only one bp in the list for that file,line
        # pair, then remove the breaks entry
        for bp in Breakpoint.bplist[filename, lineno][:]:
            debug("delete Me")
            bp.deleteMe()
        if (filename, lineno) not in Breakpoint.bplist:
            debug("delete self.breaks")
            l = self.breaks[filename]
            l.remove(lineno)
            self.breaks[filename] = l
            #self.breaks[filename].remove(lineno)
        if not self.breaks[filename]:
            del self.breaks[filename]
        debug("self.breaks: ", self.breaks)


    def clear_bpbynumber(self, arg):
        from breakpoint import Breakpoint
        try:
            number = int(arg)
        except:
            return 'Non-numeric breakpoint number (%s)' % arg
        try:
            bp = Breakpoint.bpbynumber[number]
        except IndexError:
            return 'Breakpoint number (%d) out of range' % number
        if not bp:
            return 'Breakpoint (%d) already deleted' % number
        self.clear_break(bp.file, bp.line)

    def clear_all_file_breaks(self, filename):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        if not filename in self.breaks:
            return 'There are no breakpoints in %s' % filename
        for line in self.breaks[filename]:
            blist = Breakpoint.bplist[filename, line]
            for bp in blist:
                bp.deleteMe()
        del self.breaks[filename]

    def clear_all_breaks(self):
        from breakpoint import Breakpoint
        if not self.breaks:
            return 'There are no breakpoints'
        for bp in Breakpoint.bpbynumber:
            if bp:
                bp.deleteMe()
        #self.breaks = {}
        self.breaks.clear()   # As this is a shared dictionary it is important to use clear
    
    def get_break(self, filename, lineno):
        filename = self.canonic(filename)
        return filename in self.breaks and \
            lineno in self.breaks[filename]

    def get_breaks(self, filename, lineno):
        from breakpoint import Breakpoint
        filename = self.canonic(filename)
        #if filename in self.breaks:
        #    debug("Get_breaks: Filename", filename)
        return filename in self.breaks and \
            lineno in self.breaks[filename] and \
            Breakpoint.bplist[filename, lineno] or []

    def get_file_breaks(self, filename):
        filename = self.canonic(filename)
        if filename in self.breaks:
            return self.breaks[filename]
        else:
            return []

    def get_all_breaks(self):
        return self.breaks
    
    def cmd_show_break(self, arg):
        from breakpoint import Breakpoint
        debug("Breakpoint by number: ", Breakpoint.bpbynumber)
        debug("Breakpoint list: ", Breakpoint.bplist)
        debug("self.breaks: ", self.breaks)
        
    def cmd_break(self, arg, temporary = 0):
        from breakpoint import Breakpoint
        # break [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            if self.breaks:  # There's at least one
                print("Num Type         Disp Enb   Where", file=self.stdout)
                for bp in Breakpoint.bpbynumber:
                    if bp:
                        bp.bpprint(self.stdout)
            return
        # parse arguments; comma has lowest precedence
        # and cannot occur in filename
        filename = None
        lineno = None
        cond = None
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()
        # parse stuff before comma: [filename:]lineno | function
        colon = arg.rfind(':')
        funcname = None
        if colon >= 0:
            filename = arg[:colon].rstrip()
            f = self.lookupmodule(filename)
            if not f:
                debug('*** ', repr(filename), end=' ')
                debug('not found from sys.path')
                self.dbgcom.send_break_nosucess(filename, lineno, repr(filename)+" not found")
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError as msg:
                debug('*** Bad lineno:', arg)
                self.dbgcom.send_break_nosucess(filename, lineno, "Bad lineno")
                return
        else:
            # no colon; can be lineno or function
            try:
                lineno = int(arg)
            except ValueError:
                try:
                    func = eval(arg, self.curframe.f_globals, self.curframe_locals)
                except:
                    func = arg
                try:
                    if hasattr(func, '__func__'):
                        func = func.__func__
                    code = func.__code__
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        #debug('*** The specified object', end=' ')
                        #print(repr(arg), end=' ', file=self.stdout)
                        #print('is not a function', file=self.stdout)
                        #print('or was not found along sys.path.', file=self.stdout)
                        reason = "The specified object " + repr(arg) + \
                            "is not a function or was not found along sys.path."
                        self.dbgcom.send_break_nosucess(filename, lineno, reason)
                        return
                    funcname = ok # ok contains a function name
                    lineno = int(ln)
        if not filename:
            filename = self.defaultFile()
        # Check for reasonable breakpoint
        line = self.checkline(filename, lineno)
        if line:
            # now set the break point
            err = self.set_break(filename, line, temporary, cond, funcname)
            if err:
                #debug('***', err)
                self.dbgcom.send_break_nosucess(filename, lineno, "Error: " + str(err))
            else:
                bp = self.get_breaks(filename, line)[-1]
                #debug("Breakpoint %d at %s:%d" % (bp.number, bp.file, bp.line))
                self.dbgcom.send_break_success(bp.number, bp.file, bp.line)
    
    def checkline(self, filename, lineno):
        """Check whether specified line seems to be executable.

        Return `lineno` if it is, 0 if not (e.g. a docstring, comment, blank
        line or EOF). Warning: testing is not comprehensive.
        """
        line = linecache.getline(filename, lineno, self.curframe.f_globals)
        if not line:
            print('End of file', file=self.stdout)
            return 0
        line = line.strip()
        # Don't allow setting breakpoint at a blank line
        if (not line or (line[0] == '#') or
             (line[:3] == '"""') or line[:3] == "'''"):
            debug('*** Blank or comment')
            return 0
        return lineno
    
    def cmd_clear(self, arg):
        """Three possibilities, tried in this order:
        clear -> clear all breaks, ask for confirmation
        clear file:lineno -> clear all breaks at file:lineno
        clear bpno bpno ... -> clear breakpoints by number"""
        from breakpoint import Breakpoint
        if not arg:
            try:
                reply = input('Clear all breaks? ')
            except EOFError:
                reply = 'no'
            reply = reply.strip().lower()
            if reply in ('y', 'yes'):
                self.clear_all_breaks()
            return
        if ':' in arg:
            # Make sure it works for "clear C:\foo\bar.py:12"
            i = arg.rfind(':')
            filename = arg[:i]
            arg = arg[i+1:]
            try:
                lineno = int(arg)
            except ValueError:
                err = "Invalid line number (%s)" % arg
            else:
                err = self.clear_break(filename, lineno)
            if err: debug('***', err)
            return
        numberlist = arg.split()
        for i in numberlist:
            try:
                i = int(i)
            except ValueError:
                print('Breakpoint index %r is not a number' % i, file=self.stdout)
                continue

            if not (0 <= i < len(Breakpoint.bpbynumber)):
                debug('No breakpoint numbered', i)
                continue
            
            err = self.clear_bpbynumber(i)
            if err:
                debug('***', err)
            else:
                debug('Deleted breakpoint', i)
                self.dbgcom.send_clear_success(i)
        
    def print_stack_trace(self):
        try:
            for frame_lineno in self.stack:
                self.print_stack_entry(frame_lineno)
        except KeyboardInterrupt:
            pass
    
    def print_stack_entry(self, frame_lineno, prompt_prefix=line_prefix):
        frame, lineno = frame_lineno
        if frame is self.curframe:
            self.dbgcom.send_file_pos(self.format_stack_entry(frame_lineno, prompt_prefix))
        else:
            pass
            # I think I don't need this line, not sure however
            #sendcmd(' '+self.format_stack_entry(frame_lineno, prompt_prefix), prefix='')
        #sendcmd(self.format_stack_entry(frame_lineno, prompt_prefix), prefix='')

    def cmd_commands(self, arg):
        """Not supported yet"""
        # because epdbs implementation calls the blocking cmdloop there
    
    def interaction(self, frame, traceback):
        self.setup(frame, traceback)
        self.print_stack_entry(self.stack[self.curindex])
        #r = False
        #self.cmdloop()
        #while not r:
        #    r = self.asyncmdloop()
        self.dbgcom.get_cmd()
        self.forget()
    
# copied from pdb to make use of epdb's breakpoint implementation
def effective(file, line, frame):
    from breakpoint import Breakpoint
    """Determine which breakpoint for this file:line is to be acted upon.

    Called only if we know there is a bpt at this
    location.  Returns breakpoint that was triggered and a flag
    that indicates if it is ok to delete a temporary bp.

    """
    possibles = Breakpoint.bplist[file,line]
    for i in range(0, len(possibles)):
        b = possibles[i]
        if b.enabled == 0:
            continue
        if not bdb.checkfuncname(b, frame):
            continue
        # Count every hit when bp is enabled
        b.hits = b.hits + 1
        if not b.cond:
            # If unconditional, and ignoring,
            # go on to next, else break
            if b.ignore > 0:
                b.ignore = b.ignore -1
                continue
            else:
                # breakpoint and marker that's ok
                # to delete if temporary
                return (b,1)
        else:
            # Conditional bp.
            # Ignore count applies only to those bpt hits where the
            # condition evaluates to true.
            try:
                val = eval(b.cond, frame.f_globals,
                       frame.f_locals)
                if val:
                    if b.ignore > 0:
                        b.ignore = b.ignore -1
                        # continue
                    else:
                        return (b,1)
                # else:
                #   continue
            except:
                # if eval fails, most conservative
                # thing is to stop on breakpoint
                # regardless of ignore count.
                # Don't delete temporary,
                # as another hint to user.
                return (b,0)
    return (None, None)

def run(statement, globals=None, locals=None):
    Epdb().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Epdb().runeval(expression, globals, locals)

def runctx(statement, globals, locals):
    # B/W compatibility
    run(statement, globals, locals)

def runcall(*args, **kwds):
    return Epdb().runcall(*args, **kwds)

def set_trace():
    Epdb().set_trace(sys._getframe().f_back)

# Post-Mortem interface

def post_mortem(t=None):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
        if t is None:
            raise ValueError("A valid traceback must be passed if no "
                                               "exception is being handled")

    p = Epdb()

    p.reset()
    debug('post-mortem interaction')
    frame = sys._current_frames()[_thread.get_ident()]
    debug("Post mortem wit frame:", frame)
    p.interaction(frame, t)

def pm():
    post_mortem(sys.last_traceback)
    
    # Main program for testing

TESTCMD = 'import x; x.main()'

def test():
    run(TESTCMD)

# print help
def help():
    for dirname in sys.path:
        fullname = os.path.join(dirname, 'epdb.doc')
        if os.path.exists(fullname):
            sts = os.system('${PAGER-more} '+fullname)
            if sts: print('*** Pager exit status:', sts)
            break
    else:
        pass
        #print('Sorry, can\'t find the help file "epdb.doc"', end=' ')
        #print('along the Python search path')

def usage():
    print("usage: epdb.py scriptfile [arg] ...")
    sys.exit(2)

def main():
    #if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
    #    print("usage: epdb.py scriptfile [arg] ...")
    #    sys.exit(2)
    use_stdout = True # if True, the debugger use stdout to communicate with user
    use_uds = False # if True, the debugger uses unix domain sockets for
                    # communication with the user (e.g., gui)
    uds_file = None  # file to use for unix domain sockets
    del sys.argv[0]         # Hide "epdb.py" from argument list

    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == '--help' or sys.argv[i] == '-h':
            usage()
        elif sys.argv[i] == '--stdout':
            use_stdout = True
            use_uds = False
        elif sys.argv[i] == '--uds':
            use_uds = True
            use_stdout = False
            i += 1
            try:
                uds_file = sys.argv[i]
            except:
                usage()
        else:
            break
        i += 1
    else:
        usage()
        
    mainpyfile = sys.argv[i]  # Get script file name
    del sys.argv[0:i]   # delete all files until 
    #print("mainpyfile", mainpyfile)
    #print("udsfile", uds_file)
    if not os.path.exists(mainpyfile):
        print('Error:', mainpyfile, 'does not exist')
        sys.exit(1)
            
    # Replace pdb's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(mainpyfile)

    # Note on saving/restoring sys.argv: it's a good idea when sys.argv was
    # modified by the script being debugged. It's a bad idea when it was
    # changed by the user from the command line. There is a "restart" command
    # which allows explicit specification of command line arguments.
    if use_uds:
        epdb = Epdb(uds_file=uds_file)
    else:
        epdb = Epdb()
    while 1:
        try:
            #epdb.ic = 0
            dbg.ic = 0
            epdb._runscript(mainpyfile)
            if epdb._user_requested_quit:
                break
            break
            #print("The program finished and will be restarted")
            #print("The program has finished", dbg.ic)
            #raise EpdbPostMortem()
            ##epdb.interaction(None, None)
        except pdb.Restart:
            print("Restarting", mainpyfile, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
            # Deactivating automatic restart temporarily TODO
            break
        except SystemExit:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            frame = sys._current_frames()[_thread.get_ident()]
            debug("SystemExit exception. Frame:", frame)
            epdb.interaction(frame, t)
        except EpdbExit:
            debug('EpdbExit caught')
            break
            # sys.exit(0)
        except bdb.BdbQuit:
            debug('BdbQuit caught - Shutting servers down')
            break
        except snapshotting.ControllerExit:
            debug('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            debug('SnapshotExit caught')
            break
        except EpdbPostMortem:
            t = sys.exc_info()[2]
            print("Traceback:", t)
            traceback.print_tb(t)
            epdb.mp.quit()
            break
        except:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")

            frame = sys._current_frames()[_thread.get_ident()]
            debug("Other exception. Frame:", frame)
            t = sys.exc_info()[2]
            epdb.interaction(frame, t)
    
            #print("Post mortem debugger finished. The " + mainpyfile +
            #      " will be restarted")

# When invoked as main program, invoke the debugger on a script
if __name__ == '__main__':
    import epdb
    epdb.main()
