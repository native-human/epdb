import epdblib.debugger
import sys
import unittest
from coverage import coverage
import multiprocessing
import collections
import multiprocessing.managers
import time

class EpdbStub:
    def __init__(self, uds_file=None, dbgmods=[]):
        self.uds_file = uds_file
        self.dbgmods = dbgmods
        self.quit = False
        self.called_functions = []

    def clear_called(self):
        del self.called_functions[:]

    def called(self, funcname):
        self.called_functions.append(funcname)

    def get_called(self):
        return self.called_functions

    def in_called(self, funcname):
        return funcname in self.called_functions

    def preprompt(self):
        pass

    def set_quit(self, quit):
        self.quit = quit

    def get_quit(self):
        return self.quit

    def cmd_quit(self):
        self.set_quit(True)
        return 1

    def cmd_print(self, arg):
        self.called("cmd_print")

    def cmd_set_resources(self, args):
        self.called("cmd_set_resources")

    def cmd_snapshot(self, args, temporary=0):
        self.called("cmd_snapshot")

    def cmd_continued(self, arg):
        self.called("cmd_continued")

    def cmd_restore(self, arg):
        self.called("cmd_restore")

    def cmd_nde(self, arg):
        self.called("cmd_nde")

    def cmd_resources(self, arg):
        self.called("cmd_resources")

    def cmd_ic(self, arg):
        self.called("cmd_ic")

    def cmd_timelines(self, arg):
        self.called("cmd_timelines")

    def cmd_timeline_snapshots(self, arg):
        self.called("cmd_timeline_snapshots")

    def cmd_switch_timeline(self, arg):
        self.called("cmd_switch_timeline")

    def cmd_current_timeline(self, arg):
        self.called("cmd_current_timeline")

    def cmd_newtimeline(self, arg):
        self.called("cmd_newtimeline")

    def cmd_mode(self, arg):
        self.called("cmd_mode")

    def cmd_ron(self, arg):
        self.called("cmd_ron")

    def cmd_roff(self, arg):
        self.called("cmd_roff")

    def cmd_rstep(self, arg):
        self.called("cmd_rstep")

    def cmd_rnext(self, arg):
        self.called("cmd_rnext")

    def cmd_rcontinue(self, arg):
        self.called("cmd_rcontinue")

    def cmd_step(self, arg):
        self.called("cmd_step")

    def cmd_next(self, arg):
        self.called("cmd_next")

    def cmd_continue(self, arg):
        self.called("cmd_continue")

    def cmd_return(self, arg):
        self.called("cmd_return")

    def cmd_activate_snapshot(self, arg):
        self.called("cmd_active_snapshot")

    def cmd_show_break(self, arg):
        self.called("cmd_show_break")

    def cmd_break(self, arg, temporary=0):
        self.called("cmd_break")

    def cmd_clear(self, arg):
        self.called("cmd_clear")

    def cmd_commands(self, arg):
        self.called("cmd_commands")

class EpdbManager(multiprocessing.managers.BaseManager):
    """Make EpdbStub shared with the unittest process, so
    the test_* can access the data of it"""
    pass
EpdbManager.register('EpdbStub', EpdbStub)

class Connection2Stdin:
    def __init__(self, connection):
        self.connection = connection
        self.deque = collections.deque()
        self.buffer = ""

    def receive_from_connection(self):
        r = self.connection.recv()
        self.buffer = self.buffer + r
        sp = self.buffer.split("\n")
        for e in sp[:-1]:
            self.deque.append(e)
        self.buffer = sp[-1]

    def readline(self):
        line = None
        while line is None:
            if len(self.deque) > 0:
                line = self.deque.popleft() + '\n'
            else:
                self.receive_from_connection()
        return line

    def custom_read(self):
        """Read whatever the queue have and make at most on receive"""
        if len(self.deque) > 0:
            line = self.deque.popleft() + '\n'
            return line

        self.receive_from_connection()

        if len(self.deque) > 0:
            line = self.deque.popleft() + '\n'
            return line

        ret = self.buffer
        self.buffer = ""
        return ret

class Connection2Stdout:
    def __init__(self, connection):
        self.connection = connection

    def write(self, string):
        #print("write:", string, type(string))
        self.connection.send(string)
        return len(string)

    def flush(self):
        pass

class StdComTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = EpdbManager()
        self.manager.start()
        self._orig_epdb_cls = epdblib.debugger.Epdb
        #epdblib.debugger.Epdb = EpdbStub
        self.debugger = epdblib.debugger.Epdb = self.manager.EpdbStub()
        self.manager = multiprocessing.Manager()
        self.parent_cnx, self.client_cnx = multiprocessing.Pipe()
        self.process = multiprocessing.Process(target=self.std_communication, args=(self.client_cnx, self.parent_cnx))
        self.process.start()
        self.client_cnx.close()
        self.stdout = Connection2Stdout(self.parent_cnx)
        self.stdin = Connection2Stdin(self.parent_cnx)

    def tearDown(self):
        if self.process and self.process.is_alive():
            self.process.terminate()
        epdblib.debugger.Epdb = self._orig_epdb_cls
        self.manager.shutdown()

    def std_communication(self, client_cnx, parent_cnx):
        parent_cnx.close()
        stdin = Connection2Stdin(client_cnx)
        stdout = Connection2Stdout(client_cnx)
        if 'epdblib.communication' in sys.modules:
            del sys.modules['epdblib.communication']
        self.cov = coverage(source=["epdblib"], cover_pylib=True)
        self.cov.start()
        import epdblib.communication
        dbg = self.debugger
        com = epdblib.communication.StdDbgCom(dbg, stdin=stdin, stdout=stdout)
        while not dbg.get_quit():
            com.get_cmd()

        self.cov.stop()
        self.cov.save()

    def test_std_com(self):
        output = self.stdin.custom_read()
        for name in ['step', 'rstep', 'rnext', 'rcontinue', 'next', 'continue',
                     'print', 'set_resources', 'snapshot', 'restore',
                     'continued', 'nde', 'resources', 'ic', 'timelines',
                     'timeline_snapshots', 'switch_timeline',
                     'current_timeline', 'newtimeline', 'mode', 'ron', 'roff']:
            print(name, file=self.stdout)
            output = self.stdin.custom_read()
            self.assertIn("cmd_"+name, self.debugger.get_called())
            self.debugger.clear_called()
        print("quit", file=self.stdout)
        self.process.join(timeout=1)
        self.assertEqual(self.debugger.get_quit(), True)
        self.assertFalse(self.process.is_alive())

if __name__ == '__main__':
    unittest.main()
