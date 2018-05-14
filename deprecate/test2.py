#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/1 22:51
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : test2.py
# @Software: PyCharm

from stockclib.omServ import generate_logger
import logging

buy_logger = generate_logger('buyside', 'abc.log', logging.INFO)


class A(object):
    def __init__(self, arg):
        self.name = arg

    def pp(self):
        print(self.name)


class B(A):
    def __init__(self, arg):
        super(B, self).__init__(arg)


if __name__ == '__main__':
    a = list(range(20))
    buy_logger.info("data is name {0}".format(a))
    b = B('ass')
    b.pp()