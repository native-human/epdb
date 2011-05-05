#!/usr/bin/env python

from epdblib.shareddict import DictProxy
from epdblib.shareddict import ListProxy
from epdblib.debug import debug
from epdblib import dbg

import sys

class Bp:
    def __init__(self, manager, number, file, line, temporary=0, cond=None, funcname=None):
        ""
        self.funcname = funcname
        # Needed if funcname is not None.
        self.func_first_executable_line = None
        self.file = file
        self.line = line
        self.temporary = temporary
        self.cond = cond
        self.enabled = 1
        self.ignore = 0
        self.hits = 0
        self.number = number
        self.manager = manager
        
    def __eq__(self, other):
        if self.number == other.number:
            return True
        return False

    def delete(self):
        self.manager.delete(self)
        
    def update(self):
        """Should be called after changes to the breakpoint"""
        self.manager.update(self)

    def enable(self):
        self.enabled = 1

    def disable(self):
        self.enabled = 0

    def bpprint(self, out=None):
        if out is None:
            out = sys.stdout
        if self.temporary:
            disp = 'del  '
        else:
            disp = 'keep '
        if self.enabled:
            disp = disp + 'yes  '
        else:
            disp = disp + 'no   '
        print('%-4dbreakpoint   %s at %s:%d' % (self.number, disp,
                                                       self.file, self.line), file=out)
        if self.cond:
            print('\tstop only if %s' % (self.cond,), file=out)
        if self.ignore:
            print('\tignore next %d hits' % (self.ignore), file=out)
        if (self.hits):
            if (self.hits > 1):
                ss = 's'
            else:
                ss = ''
            print(('\tbreakpoint already hit %d time%s' % (self.hits, ss)), file=out)

class BreakpointManager:
    def __init__(self, proxycreator):
        self.proxycreator = proxycreator
        
        self.bplist = proxycreator.create_dict("bplist") # indexed by (file, lineno) tuple 
        self.bpbynumber = proxycreator.create_list("bpbynumber")   # Each entry is None or an instance of Bpt
                                                         # index 0 is unused, except for marking an
                                                         # effective break .... see effective()
        
        self.breaks = self.proxycreator.create_dict("breaks") # breaks[filename]=[lineno,lineno,...]
        
        self.next = 1

    def breakpoint_by_number(self, number):
        return self.bpbynumber[number]

    def breakpoint_by_position(self, file, lineno):
        return self.bplist[(file, lineno)]

    def new_breakpoint(self, file, line, temporary=0, cond=None, funcname=None):
        """Creates a new breakpoint and adds it to the container"""
        bp = Bp(self, self.next, file, line, temporary, cond, funcname)
        
        self.next += 1
        
        self.bpbynumber.append(bp)
        if (file, line) in self.bplist:
            self.bplist[file, line].append(bp)
        else:
            self.bplist[file, line] = [bp]
            
        if not bp.file in self.breaks:
            self.breaks[file] = []
        list = self.breaks[file]
        if not line in list:
            list.append(line)
            self.breaks[file] = list  # This is necessary for the distributed version
        
        return bp

    def update(self, breakpoint):
        "Updates the breakpoint in the remote system"
        self.bpbynumber[breakpoint.number] = breakpoint
        do_break = False
        for key in self.bplist:
            bplist = self.bplist[key]
            for i,bp in enumerate(bplist):
                if bp.number == breakpoint.number:
                    bplist[i] = bp
                    self.bplist[key] = bplist
                    do_break = True
                    break
            if do_break:
                break
        l = self.bplist[(bp.file, bp.line)]

    def delete(self, bp):
        filename = bp.file
        lineno = bp.line
        if not filename in self.breaks:
            return 'There are no breakpoints in %s' % filename
        if lineno not in self.breaks[filename]:
            return 'There is no breakpoint at %s:%d' % (filename, lineno)
        # If there's only one bp in the list for that file,line
        # pair, then remove the breaks entry
        #for b in self.bplist[filename, lineno][:]:
        #    index = (b.file, b.line)
        #    self.bpbynumber[b.number] = None   # No longer in list
        #    l = self.bplist[index]
        #    l.remove(b)
        #    self.bplist[index] = l # needed for distributed version
        #    if not self.bplist[index]:
        #        # No more bp for this f:l combo
        #        del self.bplist[index]
        self.bpbynumber[bp.number] = None
        l = self.bplist[filename, lineno]
        l.remove(bp)
        if l == []:
            del self.bplist[filename, lineno]
        else:
            self.bplist[filename, lineno] = l # needed for distributed version

        if (filename, lineno) not in self.bplist:
            self.breaks[filename].remove(lineno)
        if self.breaks[filename] == []:
            del self.breaks[filename]

    def clear_break(self, filename, lineno):
        breakpoints = self.breakpoint_by_position(filename, lineno)
        for bp in breakpoints:
            self.delete(bp)
    
    def clear_all_file_breaks(self, filename):
        for line in self.breaks[filename]:
            blist = self.bplist[filename, line]
            for b in blist:
                index = (b.file, b.line)
                self.bpbynumber[b.number] = None   # No longer in list
                l = self.bplist[index]
                l.remove(b)
                self.bplist[index] = l # needed for distributed version
                if not self.bplist[index]:
                    # No more bp for this f:l combo
                    del self.bplist[index]
        del self.breaks[filename]

    def bp_exists(self, filename, lineno):
        return lineno in self.breaks

    def file_has_breaks(self, filename):
        return filename in self.breaks
    
    def any_break_exists(self):
        if self.breaks == {}:
            return False
        return True

    def clear_all_breaks(self):
        for bp in self.bpbynumber:
            if bp:
                index = (bp.file, bp.line)
                self.bpbynumber[bp.number] = None   # No longer in list
                l = self.bplist[index]
                l.remove(bp)
                self.bplist[index] = l # needed for distributed version
                if not self.bplist[index]:
                    # No more bp for this f:l combo
                    del self.bplist[index]
                bp.deleteMe()
        self.breaks.clear()

    # TODO: better rename this to has_break
    #       Also check if it is even needed
    def get_break(self, filename, lineno):  
        return filename in self.breaks and lineno in self.breaks[filename]
        
    def get_breaks(self, filename, lineno):
        # TODO simplify this difficult expression
        return filename in self.breaks and \
            lineno in self.breaks[filename] and \
            self.bplist[filename, lineno] or []

    def get_file_breaks(self, filename):
        if filename in self.breaks:
            return self.breaks[filename]
        else:
            return []

    def get_all_breaks(self):
        return self.breaks

    def checkfuncname(self, b, frame):
        """Check whether we should break here because of `b.funcname`."""
        if not b.funcname:
            # Breakpoint was set via line number.
            if b.line != frame.f_lineno:
                # Breakpoint was set at a line with a def statement and the function
                # defined is called: don't break.
                return False
            return True
    
        # Breakpoint set via function name.
    
        if frame.f_code.co_name != b.funcname:
            # It's not a function call, but rather execution of def statement.
            return False
    
        # We are in the right frame.
        if not b.func_first_executable_line:
            # The function is entered for the 1st time.
            b.func_first_executable_line = frame.f_lineno
            b.update()
    
        if  b.func_first_executable_line != frame.f_lineno:
            # But we are not at the first line number: don't break.
            return False
        return True
    
    # copied from pdb to make use of epdb's breakpoint implementation
    def effective(self, file, line, frame):
        """Determine which breakpoint for this file:line is to be acted upon.
    
        Called only if we know there is a bpt at this
        location.  Returns breakpoint that was triggered and a flag
        that indicates if it is ok to delete a temporary bp.
    
        """
        possibles = self.bplist[file, line]
        for i in range(0, len(possibles)):
            b = possibles[i]
            if b.enabled == 0:
                continue
            if not self.checkfuncname(b, frame):
                continue
            # Count every hit when bp is enabled
            b.hits = b.hits + 1
            b.update()
            if not b.cond:
                # If unconditional, and ignoring,
                # go on to next, else break
                if b.ignore > 0:
                    b.ignore = b.ignore -1
                    b.update()
                    continue
                else:
                    # breakpoint and marker that's ok
                    # to delete if temporary
                    return (b, 1)
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
                            return (b, 1)
                    # else:
                    #   continue
                except:
                    # if eval fails, most conservative
                    # thing is to stop on breakpoint
                    # regardless of ignore count.
                    # Don't delete temporary,
                    # as another hint to user.
                    return (b, 0)
        return (None, None)
        
    def findnextbreakpointic(self):
        """Looks for the next ic that has a breakpoint. It only looks at executed
        instruction counts. Returns -1 if nothing was found"""
        continued = dbg.current_timeline.get_continue()
        #from epdblib.breakpoint import Breakpoint
        bestic = -1
        for bp in self.bplist:
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
        #from epdblib.breakpoint import Breakpoint
        bestic = 0
        for bp in self.bplist:
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
    
    def show(self):
        bplist = ""
        for k in self.bplist:
            bplist += "{}:".format(k)
            for e in self.bplist[k]:
                bplist += "%s, "%e
        print(bplist)
        
        bpbynumber = ""
        for b in self.bpbynumber:
            if b:
                bplist += "%s "%b.number
        print(bpbynumber)

class LocalBreakpointManager(BreakpointManager):
    def __init__(self):        
        self.bplist = {} # indexed by (file, lineno) tuple 
        self.bpbynumber = [None]   # Each entry is None or an instance of Bpt
                                                         # index 0 is unused, except for marking an
                                                         # effective break .... see effective()
        self.breaks = {} # breaks indexed by filename
        self.next = 1

#class Breakpoint:
#
#    """Breakpoint class
#
#    Implements temporary breakpoints, ignore counts, disabling and
#    (re)-enabling, and conditionals.
#
#    Breakpoints are indexed by number through bpbynumber and by
#    the file,line tuple using bplist.  The former points to a
#    single instance of class Breakpoint.  The latter points to a
#    list of such instances since there may be more than one
#    breakpoint per line.
#
#    """
#
#    # XXX Keeping state in the class is a mistake -- this means
#    # you cannot have more than one active Bdb instance.
#
#    next = 1        # Next bp to be assigned
#    #bplist = {}     # indexed by (file, lineno) tuple
#    #bpbynumber = [None] # Each entry is None or an instance of Bpt
#                # index 0 is unused, except for marking an
#                # effective break .... see effective()
#
#    bplist = DictProxy('bplist', sockfile=dbg.shareddict_sock)
#    bpbynumber = ListProxy('bpbynumber', sockfile=dbg.shareddict_sock)
#
#    def __init__(self, file, line, temporary=0, cond=None, funcname=None):
#        self.funcname = funcname
#        # Needed if funcname is not None.
#        self.func_first_executable_line = None
#        self.file = file    # This better be in canonical form!
#        self.line = line
#        self.temporary = temporary
#        self.cond = cond
#        self.enabled = 1
#        self.ignore = 0
#        self.hits = 0
#        self.number = Breakpoint.next
#        Breakpoint.next = Breakpoint.next + 1
#        # Build the two lists
#        self.bpbynumber.append(self)
#        if (file, line) in self.bplist:
#            self.bplist[file, line].append(self)
#        else:
#            self.bplist[file, line] = [self]
#
#    def __eq__(self, other):
#        if self.number == other.number:
#            return True
#        return False
#
#    def deleteMe(self):
#        index = (self.file, self.line)
#        self.bpbynumber[self.number] = None   # No longer in list
#        #debug("remove called on", self.bplist[index])
#        l = self.bplist[index]
#        l.remove(self)
#        self.bplist[index] = l
#        #self.bplist[index].remove(self)
#        if not self.bplist[index]:
#            # No more bp for this f:l combo
#            #debug('call dell on ', self.bplist)
#            del self.bplist[index]
#
#    def enable(self):
#        self.enabled = 1
#
#    def disable(self):
#        self.enabled = 0
#
#    def bpprint(self, out=None):
#        if out is None:
#            out = sys.stdout
#        if self.temporary:
#            disp = 'del  '
#        else:
#            disp = 'keep '
#        if self.enabled:
#            disp = disp + 'yes  '
#        else:
#            disp = disp + 'no   '
#        print('%-4dbreakpoint   %s at %s:%d' % (self.number, disp,
#                                                       self.file, self.line), file=out)
#        if self.cond:
#            print('\tstop only if %s' % (self.cond,), file=out)
#        if self.ignore:
#            print('\tignore next %d hits' % (self.ignore), file=out)
#        if (self.hits):
#            if (self.hits > 1): ss = 's'
#            else: ss = ''
#            print(('\tbreakpoint already hit %d time%s' %
#                          (self.hits, ss)), file=out)