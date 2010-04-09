#!/usr/bin/env python

#from random import randint
from random import randint as rand
import token as blah
import sys
import __dbg

print(sys.path)

#import builtins

# print('ahhlsdk')
print(rand(0, 10))

__dbg.mode = 'replay'

print(rand(0,10))

__dbg.mode = 'normal'

print(rand(0, 10))

__dbg.mode = 'replay'

print(rand(0,10))