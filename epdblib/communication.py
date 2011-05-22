import socket
import string
import epdblib.asyncmd
import io
import sys

class UdsDbgCom():
    def __init__(self, debugger, filename):
        self.debugger = debugger
        self.prompt = '(Epdb) '
        self.aliases = {}
        self.filename = filename

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(filename)
        self.cmdqueue = []
        self.identchars = string.ascii_letters + string.digits + '_'

    def set_debugger(self, debugger):
        self.debugger = debugger

    def do_p(self, arg):
        return self.debugger.cmd_print(arg)
    do_print = do_p

    def do_set_resources(self, arg):
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

    def do_pid(self, arg):
        return self.debugger.cmd_pid()

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
            #print("socket.error")
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

            firstline, _, line = line.partition(b"\r\n")
            firstline = firstline.decode("UTF-8")
            firstline = firstline.rstrip('\r\n')
            #print("Received Line:", firstline)
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
        self.send("switched to timeline#" + timeline_name + "\r\n")

    def send_newtimeline_success(self, name):
        self.send("newtimeline successful#"+name+"\r\n")

    def send_file_pos(self, formatted_line):
        self.send('lineinfo#' + formatted_line + '\r\n')

    def send_expect_input(self):
        self.send("expect input#\r\n")

    def send_stdout(self, stdout):
        self.send("clear_stdout#\r\n")
        for line in stdout:
            self.send("add_stdout_line#"+line+'\r\n')

    def send_break_nosuccess(self, filename, lineno, reason):
        self.send("break nosuccess#" + str(filename) + "#" + str(lineno) + \
                  "#" + str(reason)+ "\r\n")

    def send_break_success(self, number, filename, lineno):
        self.send("break success#" + str(number) + "#" + str(filename) + \
                  "#" + str(lineno)+ "\r\n")

    def send_clear_success(self, number):
        self.send("clear success#" + str(number)+ "\r\n")

    def send_program_finished(self):
        self.send("program finished#" + "\r\n")

    def send_message(self, message):
        self.send("message#" + message + "\r\n")

    def send_debugmessage(self, message):
        self.send("debugmessage#" + message + "\r\n")

    def send_stopped(self):
        self.send("stopped#")

class StdDbgCom(epdblib.asyncmd.Asyncmd):
    def __init__(self, debugger, stdin=None, stdout=None):
        epdblib.asyncmd.Asyncmd.__init__(self, stdin=stdin, stdout=stdout)
        self.debugger = debugger
        self.prompt = '(Epdb) '
        self.aliases = {}

    def do_p(self, arg):
        return self.debugger.cmd_print(arg)
    do_print = do_p

    def do_set_resources(self, arg):
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

    def do_pid(self, arg):
        return self.debugger.cmd_pid()

    def precmd(self, line):
        """Handle alias expansion and ';;' separator."""
        if not line:
            return
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
        self.send_raw("var#", varname, "#", value, '#', sep='')

    def send_varerr(self, varname):
        self.send_raw("varerror#", varname)

    def send_synterr(self, file, ic):
        self.send_raw("syntax_error", file, ic, '', sep='#')

    def send_lastline(self, line):
        self.send_raw("> " + line, prefix="")

    def send_resources(self, resources):
        # resources [(resource_type, resource_location, [(id, ic), ...]), ...]
        self.send_raw("show resources#")
        for rtype, rloc, rlist in resources:
            self.send_raw('resource#', rtype, '#', rloc, '#', sep='')
            for rid, ric in rlist:
                self.send_raw('resource_entry#', rtype, '#', rloc, '#', rid, '#', ric, '#', sep='')

    def send_timeline_snapshots(self, snapshot_list):
        self.send_raw("timeline_snapshots#")
        for snapshot in snapshot_list:
            self.send_raw('tsnapshot#', snapshot.id, '#', snapshot.ic, '#', sep='')

    def send_timeline_switched(self, timeline_name):
        self.send_raw("Switched to timeline#" + timeline_name)

    def send_newtimeline_success(self, name):
        self.send_raw("newtimeline successful")

    def send_file_pos(self, formatted_line):
        self.send_raw('>', formatted_line, prefix='')

    def send_expect_input(self):
        self.send_raw("expect input#")

    def send_stdout(self, stdout):
        self.send_raw("-->")
        self.send_raw(stdout, prefix="#->", end='')

    def send_break_nosuccess(self, filename, lineno, reason):
        self.send_raw("error while making breakpoint")

    def send_break_success(self, number, filename, lineno):
        self.send_raw("breakpoint made")

    def send_program_finished(self):
        self.send_raw("Program has finished")

    def send_message(self, message):
        self.send_raw("message:" + message)

    def send_debugmessage(self, message):
        self.send_raw("debug: " + message)

    def send_clear_success(self, number):
        self.send_raw("clear breakpoint" + str(number)+ "\r\n")

    def send_stopped(self):
        pass

    def send_raw(self, value, *args, sep=' ', end='\n', prefix="#"):
        output = io.StringIO()
        print(value, *args, sep=sep, end=end, file=output)
        for line in output.getvalue().splitlines():
            print(prefix + line, file=self.stdout)
