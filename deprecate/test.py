#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/1 22:31
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : test.py
# @Software: PyCharm

from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor


def A():
    pool = ThreadPoolExecutor(max_workers=2)
    result = pool.submit(lambda x, y: x + y, 2, 3)
    print(result.result())


if __name__ == '__main__':
    a = Process(target=A)
    a.start()
    a.join()
