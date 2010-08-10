import random
import builtins

for i in range(1):
    random.seed()
    builtins.print(random.randint(0,10))

def blah():
    builtins.print('blah')
    builtins.print('blupp')

builtins.print('a')
#epdb.set_trace()
blah()
builtins.print('b')
builtins.print('c')
