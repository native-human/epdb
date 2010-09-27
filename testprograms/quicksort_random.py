import random

def partition(lst, pivot):
    left = []
    right = []
    middle = []
    for i in range(len(lst)):
        e = lst.pop()
        if e < pivot:
            left.append(e)
        elif e > pivot:
            right.append(e)
        else:
            middle.append(e)
    return left, middle, right
    
def quicksort(lst):
    if len(lst) <= 1:
        return lst
    randomidx = random.randint(0,len(lst)-1)
    pivot = lst[randomidx]
    left, middle, right = partition(lst, pivot)
    left = quicksort(left)
    right = quicksort(right)
    lst.extend(left)
    lst.extend(middle)
    lst.extend(right)
    return lst

l = [random.randint(0,100) for e in range(20)]
quicksort(l)        
print(l)