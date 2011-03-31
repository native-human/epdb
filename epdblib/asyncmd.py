
import cmd
import select
import sys

class Asyncmd(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.loopstarted = False
        self.use_rawinput = False

    def cmdloop(self, intro=None):
        #print("Asyncmd", intro)
        cmd.Cmd.cmdloop(self, intro)

    def asyncmdloop(self, intro=None):
        if intro is not None:
            self.intro = intro
        if not self.loopstarted:
            #print("Loop Started")
            self.preloop()
            #print("After preloop")
            self.loopstarted = True
            if self.intro:
                self.stdout.write(str(self.intro)+"\n")
            print(self.prompt, end='')
            sys.stdout.flush()

        #if self.use_rawinput and self.completekey:
        #    try:
        #        import readline
        #        self.old_completer = readline.get_completer()
        #        readline.set_completer(self.complete)
        #        readline.parse_and_bind(self.completekey+": complete")
        #    except ImportError:
        #        pass

        inp, _, _ = select.select([sys.stdin],[],[],0)
        if inp == []:
            return False

        #self.preloop()
        try:
            stop = None
            while not stop:
                #print("loop")
                inp, _, _ = select.select([sys.stdin],[],[],0)
                #print(inp, self.cmdqueue)
                if self.cmdqueue == [] and inp == []:
                    break
                #print("Success")
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    if self.use_rawinput:
                        try:
                            line = input()
                        except EOFError:
                            line = 'EOF'
                    else:
                        line = self.stdin.readline()
                        if not len(line):
                            line = 'EOF'
                        else:
                            line = line.rstrip('\r\n')
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
                if not stop:
                    print(self.prompt, end='')
                    sys.stdout.flush()
        finally:
            pass
            #if self.use_rawinput and self.completekey:
            #    try:
            #        import readline
            #        readline.set_completer(self.old_completer)
            #    except ImportError:
            #        pass
        if stop:
            self.loopstarted = False
            self.postloop()
            return True
        return False

if __name__ == '__main__':
    print("Hallo Welt")
    inp, _, _ = select.select([sys.stdin],[],[],0)
    print(inp)

    class TestAsyncmd(Asyncmd):
        def do_quit(self, args):
            print("Quit")
            return 1
        def do_step(self, args):
            return
        def preloop(self):
            print("Preloop")
        def precmd(self, line):
            print("Precmd")
            return line
        def postloop(self):
            print("Postloop")
            sys.stdout.flush()
        #def postcmd(self):
        #    print("Postcmd")

    cmd = TestAsyncmd()

    #cmd.cmdloop()
    #sys.exit(0)
    #i = 0
    r = False
    while not r:
        r = cmd.asyncmdloop()
        #print(i)
        #i = i+1
    #print(r)

    #inp = [None]
    #while inp != []:
    #    inp, _, _ = select.select([sys.stdin],[],[],0)
    #    sys.stdin.read(1)
    #    #print(sys.stdin.read(1), end='\n')
