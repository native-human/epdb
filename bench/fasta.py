# The Computer Language Benchmarks Game
# http://shootout.alioth.debian.org/
#
# modified by Ian Osgood
# modified again by Heinrich Acker
# modified by Justin Peel
# modified by Mariano Chouza
# 2to3

import sys, bisect, array

alu = (
   'GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGG'
   'GAGGCCGAGGCGGGCGGATCACCTGAGGTCAGGAGTTCGAGA'
   'CCAGCCTGGCCAACATGGTGAAACCCCGTCTCTACTAAAAAT'
   'ACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCA'
   'GCTACTCGGGAGGCTGAGGCAGGAGAATCGCTTGAACCCGGG'
   'AGGCGGAGGTTGCAGTGAGCCGAGATCGCGCCACTGCACTCC'
   'AGCCTGGGCGACAGAGCGAGACTCCGTCTCAAAAA')

iub = list(zip('acgtBDHKMNRSVWY', [0.27, 0.12, 0.12, 0.27] + [0.02]*11))

homosapiens = [
    ('a', 0.3029549426680),
    ('c', 0.1979883004921),
    ('g', 0.1975473066391),
    ('t', 0.3015094502008),
]

IM = 139968
INITIAL_STATE = 42

def makeCumulative(table):
    P = []
    C = []
    prob = 0.
    for char, p in table:
        prob += p
        P += [prob]
        C += [char]
    return (P, C)

randomGenState = INITIAL_STATE
randomLUT = None
def makeRandomLUT():
    global randomLUT
    ia = 3877; ic = 29573
    randomLUT = [(s * ia + ic) % IM for s in range(IM)]

def makeLookupTable(table):
    bb = bisect.bisect
    probs, chars = makeCumulative(table)
    imf = float(IM)
    return [chars[bb(probs, i / imf)] for i in range(IM)]

def repeatFasta(src, n):
    width = 60
    r = len(src)
    s = src + src + src[:n % r]
    for j in range(n // width):
        i = j*width % r
        print(s[i:i+width])
    if n % width:
        print(s[-(n % width):])

def randomFasta(table, n):
    global randomLUT, randomGenState
    width = 60
    rgs = randomGenState
    rlut = randomLUT
    
    lut = makeLookupTable(table)
    big_buffer = []
    ba = big_buffer.append
    
    for i in range(n):
        rgs = rlut[rgs]
        ba(lut[rgs])
    
    s = ''.join(big_buffer)
    for i in range(width, n, width):
        print(s[i-width:i])
    print(s[i:])
    
    randomGenState = rgs

def main():
    n = int(sys.argv[1])

    makeRandomLUT()

    print('>ONE Homo sapiens alu')
    repeatFasta(alu, n*2)

    print('>TWO IUB ambiguity codes')
    randomFasta(iub, n*3)

    print('>THREE Homo sapiens frequency')
    randomFasta(homosapiens, n*5)
    
main()
