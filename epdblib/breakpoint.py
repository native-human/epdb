#!/usr/bin/env python

from shareddict import DictProxy
from shareddict import ListProxy
from debug import debug

import sys

class Breakpoint:

    """Breakpoint class

    Implements temporary breakpoints, ignore counts, disabling and
    (re)-enabling, and conditionals.

    Breakpoints are indexed by number through bpbynumber and by
    the file,line tuple using bplist.  The former points to a
    single instance of class Breakpoint.  The latter points to a
    list of such instances since there may be more than one
    breakpoint per line.

    """

    # XXX Keeping state in the class is a mistake -- this means
    # you cannot have more than one active Bdb instance.

    next = 1        # Next bp to be assigned
    #bplist = {}     # indexed by (file, lineno) tuple
    #bpbynumber = [None] # Each entry is None or an instance of Bpt
                # index 0 is unused, except for marking an
                # effective break .... see effective()

    bplist = DictProxy('bplist')
    bpbynumber = ListProxy('bpbynumber')

    def __init__(self, file, line, temporary=0, cond=None, funcname=None):
        self.funcname = funcname
        # Needed if funcname is not None.
        self.func_first_executable_line = None
        self.file = file    # This better be in canonical form!
        self.line = line
        self.temporary = temporary
        self.cond = cond
        self.enabled = 1
        self.ignore = 0
        self.hits = 0
        self.number = Breakpoint.next
        Breakpoint.next = Breakpoint.next + 1
        # Build the two lists
        self.bpbynumber.append(self)
        if (file, line) in self.bplist:
            self.bplist[file, line].append(self)
        else:
            self.bplist[file, line] = [self]

    def __eq__(self, other):
        if self.number == other.number:
            return True
        return False

    def deleteMe(self):
        index = (self.file, self.line)
        self.bpbynumber[self.number] = None   # No longer in list
        #debug("remove called on", self.bplist[index])
        l = self.bplist[index]
        l.remove(self)
        self.bplist[index] = l
        #self.bplist[index].remove(self)
        if not self.bplist[index]:
            # No more bp for this f:l combo
            #debug('call dell on ', self.bplist)
            del self.bplist[index]

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
            if (self.hits > 1): ss = 's'
            else: ss = ''
            print(('\tbreakpoint already hit %d time%s' %
                          (self.hits, ss)), file=out)
