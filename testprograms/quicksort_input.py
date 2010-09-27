import random

def input_number(prompt="", error_prompt="Try again", value_list=None):
    number = None
    while True:
        line = input(prompt)
        try:
            number = int(line)
            if value_list or number in value_list:
                return number
        except ValueError:
            pass
        print(error_prompt)
        continue

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
    print("List to sort: ", lst)
    pivot = input_number(prompt="choose pivot: ", value_list=lst)
    left, middle, right = partition(lst, pivot)
    print("partitioned", left, middle, right)
    left = quicksort(left)
    right = quicksort(right)
    lst.extend(left)
    lst.extend(middle)
    lst.extend(right)
    return lst

l = [random.randint(0,100) for e in range(20)]
quicksort(l)
print(l)