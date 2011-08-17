import pdb
import sys
import linecache
from reprlib import Repr
import os
import os.path
import epdblib.snapshotting
import builtins
import _thread
import configparser
import tempfile
import epdblib.resources
import time
import epdblib.communication
from epdblib.debug import debug
import imp
import epdblib.importer
import epdblib.basedebugger
import shutil
import epdblib.breakpoint
import operator

from epdblib import dbg

dbgpath = None
resources = None
resource_paths = None

_repr = Repr()
_repr.maxstring = 200
_saferepr = _repr.repr

line_prefix = '\n-> '

def readconfig():
    global dbgpath
    global resources
    global resource_paths
    sys.path = origpath
    try:
        config = configparser.ConfigParser()
        config.read(os.path.expanduser("~/.config/epdb.conf"))
        dbgmods = list(config['PATHS'].values())
        resources = list(config['RESOURCES'].values())
        resource_paths = list(config['RESOURCE_PATHS'].values())
    except:
        pass
    dbgpath = dbgmods

origpath = sys.path[:]
readconfig()

__pythonimport__ = builtins.__import__

__all__ = ["run", "pm", "Epdb", "runeval", "runcall", "set_trace",
           "post_mortem"]

mode = 'normal'

def getmodulename(path):
    """Get the module name, suffix, mode, and module type for a given file."""
    filename = os.path.basename(path)
    suffixes = [(-len(suffix), suffix, mode, mtype)
                for suffix, mode, mtype in imp.get_suffixes()]
    suffixes.sort() # try longest suffixes first, in case they overlap
    for neglen, suffix, mode, mtype in suffixes:
        if filename[neglen:] == suffix:
            return filename[:neglen]
            #return ModuleInfo(filename[:neglen], suffix, mode, mtype)

def path_is_module(filename, module):
    suffixes = [(-len(suffix), suffix, mode, mtype)
                for suffix, mode, mtype in imp.get_suffixes()]
    suffixes.sort() # try longest suffixes first, in case they overlap
    modulepath = os.path.join(*module.split('.'))
    sepmodulepath = os.path.join('/', modulepath)
    initmodulepath = os.path.join(sepmodulepath, "__init__")
    for neglen, suffix, mode, mtype in suffixes:
        if filename == modulepath + suffix or \
           filename.endswith(sepmodulepath + suffix) or \
           filename.endswith(initmodulepath + suffix):
            return True
    return False

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

class Epdb(epdblib.basedebugger.BaseDebugger):
    def __init__(self, com=None, dbgmods=[]):
        epdblib.basedebugger.BaseDebugger.__init__(self, skip=dbg.skipped_modules)

        self.send_preprompt = False # whether the debugger should send time,
                                    # ic, and mode before giving prompt

        if not com:
            dbg.dbgcom = self.dbgcom = epdblib.communication.StdDbgCom(self)
        else:
            dbg.dbgcom = self.dbgcom = com
            self.dbgcom.set_debugger(self)
            self.send_preprompt = True
            #dbg.dbgcom = self.dbgcom = epdblib.communication.UdsDbgCom(self, uds_file)
        self.dbgmods = dbgmods

        self.aliases = {}
        self.mainpyfile = ''
        self._wait_for_mainpyfile = 0

        self.commands = {} # associates a command list to breakpoint numbers
        self.commands_doprompt = {} # for each bp num, tells if the prompt
                                    # must be disp. after execing the cmd list
        self.commands_silent = {} # for each bp num, tells if the stack trace
                                  # must be disp. after execing the cmd list
        self.commands_defining = False # True while in the process of defining
                                       # a command list
        self.commands_bnum = None # The breakpoint number for which we are
                                  # defining a list
        self.init_reversible()

    def is_skipped_module(self, module_name):
        """Extend to skip all modules that start with double underscore"""
        base = super().is_skipped_module(module_name)
        if base == True:
            return True

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

    def make_snapshot(self):
        snapshot = self.mp.make_snapshot(dbg.ic)

        snapshotdata = SnapshotData(id=snapshot.id, ic=dbg.ic)
        self.snapshots[snapshotdata.id] = snapshotdata

        if not snapshot.activated:
            dbg.current_timeline.add(snapshotdata.id)

        if snapshot.activation_type == "step_forward":
            self.dbgcom.send_debugmessage("step_forward is deprecated. This activation shouldn't be used.")
        elif snapshot.activation_type == "stop_at_ic":
            self.stop_at_ic = snapshot.stop_at_ic
            self.running_mode = "stop_at_ic"
            if dbg.ic == dbg.current_timeline.get_max_ic():
                dbg.mode = 'normal'
            else:
                dbg.mode = 'replay'
            if snapshot.stop_at_ic == dbg.ic:
                return 1
            return
        elif snapshot.activation_type == "stopatnocalls":
            self.set_next(self.curframe)
            self.stopnocalls = snapshot.nocalls
            self.running_mode = 'next'
            dbg.mode = 'replay'
            return 1
        elif snapshot.activation_type == "continue":
            self.set_continue()
            #self.set_step()
            self.running_mode = 'continue'
            dbg.mode = "replay"
            return 1
        else:
            # This typically happens if the snapshot is made
            return 'snapshotmade'

    def preprompt(self):
        t = time.time()
        if self.command_running_start_time:
            tdiff = t - self.command_running_start_time
        else:
            tdiff = None
        if self.send_preprompt:
            self.dbgcom.send_ic_mode(dbg.ic, dbg.mode)
            if self.command_running_start_time:
                #print("time: t:", t, "self.start_running_time:", self.command_running_start_time)
                self.dbgcom.send_time(tdiff)
            else:
                self.dbgcom.send_time()
        self.command_running_start_time = None

    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        #sys.path.append(dbgpath)
        sys.meta_path.append(epdblib.importer.EpdbImportFinder(debugger=self, dbgmods=['./'] + self.dbgmods + dbgpath))
        if 'builtins' in sys.modules.keys():
            del sys.modules['builtins']
        import builtins
        imp.reload(sys.modules['random'])
        imp.reload(sys.modules['time'])
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": builtins,
                                })

        # When basedebugger sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = 0
        with open(filename, "rb") as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)

        self.run(statement, __main__.__dict__)

        dbg.ic += 1
        if self._user_requested_quit:
            self.cleanup()
            return
        self.dbgcom.send_program_finished()
        dbg.mode = "post_mortem"
        self.set_resources()
        self.is_postmortem = True
        self.interaction(self.lastframe, None)

    def init_reversible(self):
        import epdblib.shareddict
        self.resources = resources
        self.resource_paths = resource_paths
        epdblib.shareddict.initialize_resources(self.resources, self.resource_paths)
        #self.command_running_start_time = time.time()
        self.lastline = ''
        self.command_running_start_time = None
        dbg.tempdir = tempfile.mkdtemp(prefix="epdb")
        os.mkdir(os.path.join(dbg.tempdir, 'stdout_resource'))
        os.mkdir(os.path.join(dbg.tempdir, 'file_resource'))
        self.mp = epdblib.snapshotting.MainProcess(tempdir=dbg.tempdir)
        self.proxycreator = epdblib.shareddict.ProxyCreator(dbg.tempdir)
        self.bpmanager = epdblib.breakpoint.BreakpointManager(self.proxycreator)
        self.ron = True

        dbg.ic = 0 # Instruction Counter

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

        #self.breaks = epdblib.shareddict.DictProxy('breaks', dbg.shareddict_sock)
        #self.snapshots = epdblib.shareddict.DictProxy('snapshots', dbg.shareddict_sock)
        self.breaks = self.proxycreator.create_dict("breaks")
        self.snapshots = self.proxycreator.create_dict("snapshots")

        dbg.current_timeline.new_resource('__stdout__', '')
        stdout_resource_manager = epdblib.resources.StdoutResourceManager()
        stdout_manager = dbg.current_timeline.create_manager(('__stdout__', ''), stdout_resource_manager)
        id = stdout_manager.save()
        dbg.current_timeline.get_resource('__stdout__', '')[dbg.ic] = id

    def set_resources(self):
        """Sets the resources for the actual position"""
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
                        self.dbgcom.send_debugmessage("Error: No key found for set_resources")
                        return
            self.dbgcom.send_debugmessage("Restoring resource {} {} {}".format(k, i, res))
            manager = dbg.current_timeline.get_manager(k)
            manager.restore(res)

    def cmd_print(self, arg):
        try:
            self.dbgcom.send_var(arg, repr(self._getval(arg)))
        except:
            self.dbgcom.send_varerr(arg)
    # make "print" an alias of "p" since print isn't a Python statement anymore

    def cmd_set_resources(self, args):
        self.set_resources()
        
    def cmd_pid(self):
        """Shows the pid of the main process"""
        self.dbgcom.send_debugmessage("pid: " + str(os.getpid()))

    def user_exception(self, frame, exc_info):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        exc_type, exc_value, exc_traceback = exc_info
        frame.f_locals['__exception__'] = exc_type, exc_value
        if exc_type == SyntaxError:
            self.dbgcom.send_synterr(exc_value[1][0], exc_value[1][1])
        self.dbgcom.send_debugmessage("interaction, because of exception: {0} {1}".format(
            exc_type, exc_value
        ))

    def add_skip_module(self, module):
        self.skip.add(module)

    def user_first(self, frame):
        dbg.ic = 0
        r = self.make_snapshot()
        self._wait_for_mainpyfile = 0
        if r == 'snapshotmade':
            self.starttime = time.time()
            return
        else:
            pass

    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if frame.f_code.co_filename == "<string>":
            return

        if hasattr(self, 'lastframe'):
            del self.lastframe
        self.lastframe = frame

        actualtime = time.time()
        if self.starttime:
            self.runningtime += actualtime - self.starttime

        dbg.ic += 1
        try:
            lineno = frame.f_lineno
        except:
            lineno = "err"
        # TODO only make snapshots in normal mode?

        if dbg.snapshottingcontrol.get_make_snapshot():
            r = self.make_snapshot()
            dbg.snapshottingcontrol.clear_make_snapshot()
            self.runningtime = 0
        elif self.runningtime >= 1 and dbg.mode == 'normal':
            r = self.make_snapshot()
            self.runningtime = 0
        
        self.lastline = "{filename}({lineno})<module>()".format(filename=frame.f_code.co_filename, lineno=frame.f_lineno)
        def setmode():
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
                l = continued[(filename, lineno)]
                l.append(dbg.ic)
                continued[(filename, lineno)] = l
            except:
                continued[(filename, lineno)] = [dbg.ic]

        if self.running_mode == 'continue':
            if dbg.mode == 'redo':
                setmode()
            if dbg.mode == 'normal':
                if self.break_here(frame):
                    setmode()
                    self.interaction(frame, None)

        elif self.running_mode == 'next':
            setmode()
            if self.break_here(frame):
                self.stopnocalls = None
                if dbg.mode == 'redo':
                    self.set_resources()
                self.interaction(frame, None)
            elif not self.stopnocalls is None and self.nocalls <= self.stopnocalls:
                if dbg.mode == 'redo':
                    self.set_resources()
                self.interaction(frame, None)

        elif self.running_mode == 'step':
            setmode()
            if dbg.mode == 'redo':
                self.set_resources()
            self.interaction(frame, None)

        elif self.running_mode == 'stop_at_ic':
            if self.stop_at_ic <= dbg.ic:
                # Stop here but some variables before stopping
                if dbg.current_timeline.get_max_ic() > dbg.ic:
                    dbg.mode = 'redo'
                else:
                    dbg.mode = 'normal'
                self.set_resources()
                self.interaction(frame, None)
            else:
                setmode()

        elif self.running_mode == 'stopafter':
            self.dbgcom.send_debugmessage("stopafter mode shouldn't be used. 33")

        else:
            self.interaction(frame, None)
        self.starttime = time.time()

    def user_call(self, frame):
        self.call_stack.append(dbg.ic)
        nextd = dbg.current_timeline.get_next()
        self.nocalls += 1
        if not dbg.ic in nextd:
            nextd[dbg.ic] = None

        if self.running_mode is None:
            if self._wait_for_mainpyfile:
                return
            self.interaction(frame, None)

    def set_continue(self):
        if not self.ron:
            return super().set_continue(self)

        # Debugger overhead needed to count instructions
        self.set_step()
        self.running_mode = 'continue'

    def cmd_snapshot(self, arg, temporary=0):
        """snapshot - makes a snapshot"""
        ic = dbg.ic
        snapshots = dbg.current_timeline.get_snapshots()
        for sid in snapshots:
            s = self.snapshots[sid]
            if ic == s.ic:
                self.dbgcom.send_debugmessage("This ic already has an instruction count")
                return

        r = self.make_snapshot()

        if r == "snapshotmade":
            self.dbgcom.send_debugmessage("Made snapshot")
            self.dbgcom.send_lastline(self.lastline)
            return

        # TODO: support other running_modes
        # Note: This works for some reason for the other modes. However,
        # I am not sure if it works in every case (e.g.: if some other command
        # sets a different mode than set_step)
        self.dbgcom.send_debugmessage("go to line: " + str(dbg.ic + max(self.stopafter, 0)))
        self.dbgcom.send_debugmessage("snapshot activated with running_mode: " + str(self.running_mode))
        if self.running_mode == 'stop_at_ic' and self.stop_at_ic == dbg.ic:
            self.preprompt()
            self.dbgcom.send_lastline(self.lastline)
            self.dbgcom.send_debugmessage("Set lastline: " + self.lastline)
            self.running_mode = None
            self.set_resources()
            return
        elif self.running_mode == 'stop_at_ic':
            return 1
        else:
            self.dbgcom.send_debugmessage("ELSE: running_mode: " + self.running_mode + " stopafter: " + str(self.stopafter))
        self.dbgcom.send_debugmessage("Snapshot return: " + str(r) + " ic: " + str(dbg.ic))
        return r

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
            rl = []
            for rid in resource:
                rl.append((rid, resource[rid]))
            rl.sort(key=operator.itemgetter(0))
            l.append((k[0], k[1], rl))
            l.sort(key=operator.itemgetter(0))
        self.dbgcom.send_resources(l)

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
            debug("Timeline '", arg, "' doesn't exist", sep='')
            return
        dbg.current_timeline.deactivate(dbg.ic)
        ic = timeline.get_ic()

        dbg.timelines.set_current_timeline(timeline.get_name())
        self.dbgcom.send_timeline_switched(timeline.get_name())
        dbg.current_timeline = timeline
        s = self.findsnapshot(ic)
        self.mp.activateic(s.id, ic)
        raise EpdbExit()

    def cmd_current_timeline(self, arg):
        """View the name of the current timeline"""
        dbg.current_timeline.show()

    def cmd_newtimeline(self, arg):
        """Create a new timeline. This allows changing the program flow from the last run"""
        if arg.strip() == '':
            self.dbgcom.send_debugmessage("You need to supply a name for the new timeline")
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
        if self.is_postmortem:
            self.cleanup() # otherwise cleanup later
        self._user_requested_quit = 1
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
        self.ron = True

    def cmd_roff(self, arg):
        """Disables reversible debugging"""
        if self.ron:
            if dbg.ic > dbg.max_ic:
                dbg.max_ic = dbg.ic
            self.ron = False
            dbg.current_timeline.deactivate(dbg.ic)

    def cmd_rstep(self, arg):
        """Steps one step backwards"""

        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return

        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)

        if dbg.ic == 0:
            self.dbgcom.send_message("At the beginning of the program. Can't step back.")
            return

        s = self.findsnapshot(dbg.ic-1)
        if s == None:
            debug("No snapshot made. Can't step back")
            return

        self.dbgcom.send_debugmessage("Activate ic {0}".format(dbg.ic))
        self.mp.activateic(s.id, dbg.ic - 1)
        raise EpdbExit()

    def cmd_rnext(self, arg):
        """Reverse a next command."""
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return

        if dbg.mode == 'post_mortem':
            self.cmd_rstep(arg)

        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)

        if dbg.ic == 0:
            self.dbgcom.send_message("At the beginning of the program. Can't step back.")
            #debug("At the beginning of the program. Can't step back")
            return

        nextic = self.rnext_ic.get(dbg.ic, dbg.ic-1)
        bpic = self.bpmanager.findprecedingbreakpointic()
        nextic = max(nextic, bpic)

        s = self.findsnapshot(nextic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return

        self.mp.activateic(s.id, nextic)
        raise EpdbExit()

    def cmd_rcontinue(self, arg):
        """Continues in backward direction"""
        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return

        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)
        if dbg.ic == 0:
            self.dbgcom.send_message("At the beginning of the program. Can't step back.")
            return

        highestic = self.bpmanager.findprecedingbreakpointic()

        s = self.findsnapshot(highestic)
        if s == None:
            debug("No snapshot made. Can't step back")
            return

        self.mp.activateic(s.id, highestic)
        raise EpdbExit()

    def set_next(self, frame):
        """Stop on the next line in or below the given frame."""
        if not self.ron:

            return epdblib.basedebugger.BaseDebugger.set_next(self, frame)
        self.set_step()
        self.running_mode = 'next'
        #self.nocalls = 0 # Increased on call - decreased on return
        self.stopnocalls = self.nocalls

    def set_step(self):
        """Stop on the next line in or below the given frame."""
        self.stopnocalls = None
        return epdblib.basedebugger.BaseDebugger.set_step(self)

    def cmd_step(self, arg):
        if self.is_postmortem:
            self.dbgcom.send_message("You are at the end of the program. You cant go forward.")
            self.dbgcom.send_finished()
            return
        if not self.ron:
            return epdblib.basedebugger.BaseDebugger.do_step(self, arg)
        if dbg.mode == 'redo':
            s = self.findsnapshot(dbg.ic+1)
            if s == None:
                return
            if s.ic <= dbg.ic:
                self.set_step()
                self.running_mode = 'step'
                return 1
            else:
                self.mp.activateic(s.id, dbg.ic+1)
                raise EpdbExit()
        else:
            self.set_step()
            self.running_mode = 'step'
            self.command_running_start_time = time.time()
            return 1

    def cmd_next(self, arg):
        if self.is_postmortem:
            self.dbgcom.send_message("You are at the end of the program. You cant go forward.")
            self.dbgcom.send_finished()
            return
        if dbg.mode == 'redo':
            nextd = dbg.current_timeline.get_next()
            nextic = nextd.get(dbg.ic, "empty")
            bpic = self.bpmanager.findnextbreakpointic()

            if nextic == "empty":
                # There is no function call in the current line -> same as stepping
                s = self.findsnapshot(dbg.ic+1)
                nextic = dbg.ic + 1
            elif nextic is None and bpic == -1:
                # The next command has to switch to normal mode at some point
                # Use the highest available snapshot
                s = self.findsnapshot(dbg.current_timeline.get_max_ic())
                if s.ic <= dbg.ic:
                    self.set_next(self.curframe)
                    self.running_mode = 'next'
                    return 1
                else:
                    self.mp.activatenext(s.id, self.nocalls)
                    raise EpdbExit()
            else:
                # The next ends in the current timeline and no mode switch is needed.
                debug("no modeswitch next")
                if nextic is None:
                    nextic = bpic
                elif bpic == -1:
                    pass
                else:
                    nextic = min(nextic, bpic)
                s = self.findsnapshot(nextic)

            #s = self.findsnapshot(dbg.ic+1)
            if s == None:
                debug("No snapshot made. This shouldn't be")
                return
            if s.ic <= dbg.ic:
                self.set_next(self.curframe)
                self.running_mode = 'next'
                return 1
            else:
                self.mp.activateic(s.id, nextic)
                raise EpdbExit()
        else:
            self.command_running_start_time = time.time()
            #epdblib.basedebugger.BaseDebugger.set_next(self,self.curframe)
            self.set_next(self.curframe)
            return 1
    do_n = cmd_next

    def cmd_continue(self, arg):
        if self.is_postmortem:
            self.dbgcom.send_message("You are at the end of the program. You cant go forward.")
            self.dbgcom.send_finished()
            return
        if dbg.mode == 'redo':
            bestic = self.bpmanager.findnextbreakpointic()
            if bestic == -1:
                #debug("redo_cont: No future bp in executed instructions found")
                # go to the highest snapshot and continue
                s = self.findsnapshot(dbg.current_timeline.get_max_ic())
                #debug("current_ic", dbg.ic, "snapshot_ic", s.ic)
                if dbg.ic < s.ic:
                    self.mp.activatecontinue(s.id)
                    raise EpdbExit()
                else:
                    # normal continue
                    pass
            else:
                # redo continue
                # find snapshot and continue
                s = self.findsnapshot(bestic)
                self.mp.activateic(s.id, bestic)
                raise EpdbExit()
        else:
            self.command_running_start_time = time.time()
        self.set_continue()
        return 1

    def cmd_return(self, arg):
        debug("Return not implemented yet for epdb")

    def set_quit(self):
        epdblib.basedebugger.BaseDebugger.set_quit(self)

    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        try:
            callic = self.call_stack.pop()
            self.rnext_ic[dbg.ic + 1] = callic
            #dbg.current_timeline.get_rnext()[dbg.ic + 1] = callic
            next_ic = dbg.current_timeline.get_next()
            next_ic[callic] = dbg.ic + 1
        except:
            # this usually happens when the program has finished
            # or ron was set when there was something on the stack
            # in this case epdb simply fall back to step backwards.

            # In case the program ends send the information of the last line
            # executed.
            self.dbgcom.send_lastline(self.lastline)
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
            self.dbgcom.send_debugmessage('--Return--')
            self.interaction(frame, None)

    def cmd_activate_snapshot(self, arg):
        """activate the snapshot with the given id"""

        if not self.ron:
            debug("You are not in reversible mode. You can enable it with 'ron'.")
            return

        if dbg.ic > dbg.current_timeline.get_max_ic():
            dbg.current_timeline.set_max_ic(dbg.ic)

        snapshots = dbg.current_timeline.get_snapshots()
        for sid in snapshots:
            s = self.snapshots[sid]
            if s.id == int(arg):
                break
        else:
            debug("Snapshot not found in timeline")
            return

        self.mp.activateic(s.id, self.snapshots[sid].ic)
        raise EpdbExit()

    def lookupmodule(self, filename):
        """Helper function for break/clear parsing -- may be overridden.

        lookupmodule() translates (possibly incomplete) file or module name
        into an absolute file name.
        """
        if os.path.isabs(filename) and  os.path.exists(filename):
            return filename
        f = os.path.join(sys.path[0], filename)
        if  os.path.exists(f) and self.canonic(f) == self.mainpyfile:
            return f
        root, ext = os.path.splitext(filename)
        if ext == '':
            filename = filename + '.py'
        if os.path.isabs(filename):
            return filename
        for dirname in sys.path:
            while os.path.islink(dirname):
                dirname = os.readlink(dirname)
            fullname = os.path.join(dirname, filename)
            if os.path.exists(fullname):
                return fullname
        return None

    def cmd_break(self, arg, temporary = 0):
        if not arg:
            if self.breaks:  # There's at least one
                self.bpmanager.show()
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
            except ValueError:
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
                self.dbgcom.send_break_nosucess(filename, lineno, "Error: " + str(err))
            else:
                bp = self.get_breaks(filename, line)[-1]
                self.dbgcom.send_break_success(bp.number, bp.file, bp.line)

    def checkline(self, filename, lineno):
        """Check whether specified line seems to be executable.

        Return `lineno` if it is, 0 if not (e.g. a docstring, comment, blank
        line or EOF). Warning: testing is not comprehensive.
        """
        line = linecache.getline(filename, lineno, self.curframe.f_globals)
        if not line:
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
        #from epdblib.breakpoint import Breakpoint
        if not arg:
            try:
                reply = input('Clear all breaks? ')
            except EOFError:
                reply = 'no'
            reply = reply.strip().lower()
            if reply in ('y', 'yes'):
                self.manager.clear_all_breaks()
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
                #print('Breakpoint index %r is not a number' % i, file=self.stdout)
                continue
            
            # TODO don't directly access the bpmanager
            if not (0 <= i < len(self.bpmanager.bpbynumber)):
                debug('No breakpoint numbered', i)
                continue

            err = self.clear_bpbynumber(i)
            if err:
                debug('***', err)
            else:
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

    def cmd_commands(self, arg):
        """Not supported yet"""
        # because epdbs implementation calls the blocking cmdloop there

    def _getval(self, arg):
        try:
            return eval(arg, self.curframe.f_globals, self.curframe_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else:
                exc_type_name = t.__name__
            self.dbgcom.send_debugmessage("*** {}: {}".format(exc_type_name, repr(v)))
            raise

    def interaction(self, frame, traceback):
        self.setup(frame, traceback)
        self.print_stack_entry(self.stack[self.curindex])
        if dbg.mode != "post_mortem":
            self.dbgcom.send_stopped()
        else:
            self.dbgcom.send_finished()
        self.dbgcom.get_cmd()
        self.forget()

    def setup(self, f, t):
        self.forget()
        self.stack, self.curindex = self.get_stack(f, t)
        self.curframe = self.stack[self.curindex][0]
        # The f_locals dictionary is updated from the actual frame
        # locals whenever the .f_locals accessor is called, so we
        # cache it here to ensure that modifications are not overwritten.
        self.curframe_locals = self.curframe.f_locals

    def forget(self):
        self.lineno = None
        self.stack = []
        self.curindex = 0
        self.curframe = None
        
    def defaultFile(self):
        """Produce a reasonable default."""
        filename = self.curframe.f_code.co_filename
        if filename == '<string>' and self.mainpyfile:
            filename = self.mainpyfile
        return filename
    
    def cleanup(self):
        self.mp.quit()
        shutil.rmtree(dbg.tempdir)
    
def run(statement, globals=None, locals=None):
    Epdb().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Epdb().runeval(expression, globals, locals)

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
