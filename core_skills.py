import random
rand_list = [i for i in random.randint(1, 20)]

list_comprehension_below_10 = [i for i in rand_list if i < 10]

def less_than_10(x):
    return x if x < 10 else False

list_comprehension_below_10 = list(filter(less_than_10, rand_list))