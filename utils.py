def find(sequence, condition):
    for x in sequence:
        if condition(x):
            return True
    return False


def count(sequence, condition):
    i = 0
    for x in sequence:
        if condition(x):
            i = i + 1
    return i