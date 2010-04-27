#!/usr/bin/env python

import random

def quicksort(list):
    if len(list) <= 1:
        return list
    
    idx = random.randint(0, len(list)-1)
    pivot = list[idx]
    del list[idx]
    
    smaller = []
    bigger = []
    
    for e in list:
        if e < pivot:
            smaller.append(e)
        else:
            bigger.append(e)
            
    s = quicksort(smaller)
    b = quicksort(bigger)
    
    return s + [pivot] + b

print('quicksort([3,2,1,4,5]) = ', quicksort([3,2,1,4,5]))