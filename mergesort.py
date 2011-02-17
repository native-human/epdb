import builtins
from io import SEEK_SET, SEEK_CUR, SEEK_END
import math

def mergesort(f, left, right):
    def merge(left, middle, right):
        print('merge')
        nonlocal f
        f.seek(left, SEEK_SET)
        tmpf1 = builtins.open('/tmp/file1', 'w+')
        tmpf2 = builtins.open('/tmp/file2', 'w+')
        f.seek(left, SEEK_SET)
        leftpart = f.read(middle-left)
        tmpf1.write(leftpart)
        rightpart = f.read(right - middle)
        tmpf2.write(rightpart)

        tmpf1.seek(0, SEEK_SET)
        tmpf2.seek(0, SEEK_SET)
        l = tmpf1.read(1)
        r = tmpf2.read(1)
        f.seek(left, SEEK_SET)
        buffer = ''
        for i in range(right-left):
            if r == '' or l < r:
                f.write(l)
                buffer += l
                l = tmpf1.read(1)
            if l == '' or r < l:
                f.write(r)
                buffer += r
                r = tmpf2.read(1)
        tmpf1.close()
        tmpf2.close()
        print(buffer)
        print()

    if right - left == 1:
        f.read(1)
        return

    middle = left + math.trunc((right - left) / 2)

    mergesort(f, left, middle)
    mergesort(f, middle, right)
    merge(left, middle, right)


forig = builtins.open('testfile', 'r+')

f = builtins.open('testfile2', 'w+')
nocharacters = f.write(forig.read()[:-1])
forig.close()

print('nocharacters', nocharacters)
f.seek(0,SEEK_SET)
mergesort(f,0, nocharacters)
f.seek(0,0)
print('Finished: ')
print(f.read())

f.close()
