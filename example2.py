#!/usr/bin/env python

f = open("testfile2", 'r+')

print('File opened')

text = f.read()

print(text)

byteswritten = f.write('Hallo Welt\n')

print('byteswritten', byteswritten)
f.close()

print('Finish')
