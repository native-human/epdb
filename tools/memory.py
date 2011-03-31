import subprocess as sp
import tempfile
import os
import sys

tfh, tfn = tempfile.mkstemp()
print(tfn)
ps = sp.Popen(["ps", "aux"], stdout=sp.PIPE)
grep = sp.Popen(["grep", "python3"], stdin=ps.stdout, stdout=sp.PIPE)
grep2 = sp.Popen(["grep", "-v", "memory.py"], stdin=grep.stdout, stdout=sp.PIPE)
grep3 = sp.Popen(["grep", "-v", "grep"], stdin=grep2.stdout, stdout=sp.PIPE)
cut = sp.Popen(["cut", "-b", "10-15"], stdin=grep3.stdout, stdout=sp.PIPE)
line = cut.stdout.readline().strip().decode()
while line:
    #print(str(line))
    pmap = sp.Popen(["pmap", "-q", str(line)], stdout=sp.PIPE)
    sed = sp.Popen(["sed", "-e", "1d"], stdin=pmap.stdout, stdout=tfh)
    line = cut.stdout.readline().strip().decode()

os.close(tfh)

sort = sp.Popen(["sort", tfn], stdout=sp.PIPE)
uniq = sp.Popen(["uniq"], stdin=sort.stdout, stdout=sp.PIPE)
awk = sp.Popen(["awk", "{print $2}"], stdin=uniq.stdout, stdout=sp.PIPE)
sum = 0
line = awk.stdout.readline().strip().decode()
while line:
    #print(line)
    number = int(line[:-1])
    unit = line[-1]
    if unit != 'K':
        print("Error units not in KBytes")
    line = awk.stdout.readline().strip().decode()
    sum += number

print(sum)
