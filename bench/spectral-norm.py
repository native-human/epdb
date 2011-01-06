# Computer Language Benchmarks Game
# http://shootout.alioth.debian.org/
#
# Contributed by Sebastien Loisel
# Fixed by Isaac Gouy
# Sped up by Josh Goldfoot
# Dirtily sped up by Simon Descarpentries
# 2to3

from math      import sqrt

from sys       import argv

def eval_A (i, j):
    return 1.0 / ((i + j) * (i + j + 1) / 2 + i + 1)

def eval_A_times_u (u):
    resulted_list = []
    local_eval_A = eval_A

    for i in range (len (u)):
        partial_sum = 0

        for j, u_j in zip (range (len (u)), u):
            partial_sum += local_eval_A (i, j) * u_j

        resulted_list.append (partial_sum)

    return resulted_list

def eval_At_times_u (u):
    resulted_list = []
    local_eval_A = eval_A

    for i in range (len (u)):
        partial_sum = 0

        for j, u_j in zip (range (len (u)), u):
            partial_sum += local_eval_A (j, i) * u_j

        resulted_list.append (partial_sum)

    return resulted_list

def eval_AtA_times_u (u):
    return eval_At_times_u (eval_A_times_u (u))

def main():
    n = int (argv [1])
    u = [1] * n
    local_eval_AtA_times_u = eval_AtA_times_u

    for dummy in range (10):
        v = local_eval_AtA_times_u (u)
        u = local_eval_AtA_times_u (v)

    vBv = vv = 0

    for ue, ve in zip (u, v):
        vBv += ue * ve
        vv  += ve * ve

    print("%0.9f" % (sqrt(vBv/vv)))

main()
