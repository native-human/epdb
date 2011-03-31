#!/usr/bin/python3
import sys
import epdblib.debugger
import pdb
import os
import debug
import bdb
import snapshotting
import traceback
import _thread
import dbg

#TESTCMD = 'import x; x.main()'

#def test():
#    run(TESTCMD)

# print help
class UsageException(Exception):
    def __init__(self, msg=None):
        self.msg = msg

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

def usage(msg=None):
    if msg:
        print(msg)
    print("usage: epdb.py scriptfile [arg] ...")
    sys.exit(2)

def parse_args(argv):
    #if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
    #    print("usage: epdb.py scriptfile [arg] ...")
    #    sys.exit(2)
    use_stdout = True # if True, the debugger use stdout to communicate with user
    use_uds = False # if True, the debugger uses unix domain sockets for
                    # communication with the user (e.g., gui)
    uds_file = None  # file to use for unix domain sockets
    del argv[0]         # Hide "epdb.py" from argument list
    dbgmods = []
    i = 0
    while i < len(argv):
        if argv[i] == '--help' or argv[i] == '-h':
            raise UsageException()
        elif argv[i] == '--stdout':
            use_stdout = True
            use_uds = False
        elif argv[i] == '--uds':
            use_uds = True
            use_stdout = False
            i += 1
            try:
                uds_file = argv[i]
            except IndexError:
                raise UsageException("--uds needs an opened Unix Domain Socket name as an argument")
        elif argv[i] == '--dbgmods':
            i += 1
            try:
                pathname = argv[i]
            except IndexError:
                raise UsageException("--dbgmods needs a pathname as an argument")
            else:
                dbgmods.append(pathname)
        else:
            break
        i += 1
    else:
        raise UsageException("No executable given")
    
    # Note on saving/restoring sys.argv: it's a good idea when sys.argv was
    # modified by the script being debugged. It's a bad idea when it was
    # changed by the user from the command line. There is a "restart" command
    # which allows explicit specification of command line arguments.
    if use_uds:
        epdb = epdblib.debugger.Epdb(uds_file=uds_file, dbgmods=dbgmods)
    else:
        epdb = epdblib.debugger.Epdb(dbgmods=dbgmods)
    
    mainpyfile = argv[i]  # Get script file name
    del argv[0:i]   # delete all files until
        
    return epdb, mainpyfile
        
def main():
    print("sys.argv", sys.argv)
    try:
        epdb, mainpyfile = parse_args(sys.argv)
    except UsageException as e:
        usage(e.msg)
    print("mainpyfile", mainpyfile)
    #print("udsfile", uds_file)
    if not os.path.exists(mainpyfile):
        print('Error:', mainpyfile, 'does not exist')
        sys.exit(1)

    # Replace pdb's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(mainpyfile)

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
        except epdblib.debugger.EpdbExit:
            #debug('EpdbExit caught')
            break
            # sys.exit(0)
        except bdb.BdbQuit:
            debug('BdbQuit caught - Shutting servers down')
            break
        except snapshotting.ControllerExit:
            debug('ControllerExit caught')
            break
        except snapshotting.SnapshotExit:
            #debug('SnapshotExit caught')
            break
        except epdblib.debugger.EpdbPostMortem:
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
    #print(epdb, epdb.__dict__)
    epdb.main()
