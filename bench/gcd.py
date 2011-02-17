import time
starttime = time.time()
p1 = 2319**2680+2680**2319
p2 = 87*2**24582+2579
p3 = 3020255265*2**20025-1
p4 = 192201*2**666666-1
n1 = p4*p2
n2 = p2*p3
#print n1
#print n2

def gcd(a, b):
    i = 0
    a,b = max(a,b),min(a,b)
    while True:
        i += 1
        if b == 0:
            return a,i
        a,b = b, a % b
        #return gcd(b, a % b)

g,i = gcd(n1,n2)
print(i)
print(g==p2)
print("time: ",time.time() - starttime )
