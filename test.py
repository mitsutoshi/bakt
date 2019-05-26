import numpy as np
import time
from datetime import datetime, timedelta
import json
import timeit


def sum_arr_np(length):
    start = time.time()
    arr = np.arange(length)
    print(np.sum(arr))
    print("sum_arr_np: ", time.time() - start)


def sum_arr_py(length):
    start = time.time()
    arr = range(length)
    print(sum(arr))
    print("sum_arr_py: ", time.time() - start)


def add_array_np(length):
    start = time.time()
    ar = np.array([i for i in range(length)])
    print("add_array_np: ", time.time() - start)
    return ar


def add_array_py(length):
    start = time.time()
    ar = [i for i in range(length)]
    print("add_array_py: ", time.time() - start)
    return ar


if __name__ == '__main__':

    import bakt_c
    #
    # def sub(a, b):
    #     return a - b * 10 / 2
    #
    # def concat(s1, s2):
    #     s3 = s1 + s2
    #     return s3[1:]
    #
    # a = 10
    # b = 8
    # s1 = "abc"
    # s2 = "def"
    # print("python: ", timeit.timeit('sub(a, b)',        globals=globals(), number=100000))
    # print("cython: ", timeit.timeit('bakt_c.sub(a, b)', globals=globals(), number=100000))
    #
    # print("python : ", timeit.timeit('concat(s1, s2)',        globals=globals(), number=900000))
    # print("cython : ", timeit.timeit('bakt_c.concat(s1, s2)', globals=globals(), number=900000))

    arr = np.array([[1,2,3,4,5],[6,7,8,9,10]])
    for a in range(arr.shape[1]):
        print(a)
        print(arr[:, a])
        # print(arr[:, a])
