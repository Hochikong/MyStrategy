#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/1 22:10
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : strun.py.py
# @Software: PyCharm

from core import Buy
from config import *
import os

if __name__ == "__main__":
    file = open('runtime/buyside.pid', 'w')
    file.write(str(os.getpid()))
    file.close()
    s = Buy(address, port, username, passwd, database,
            geckopath, hl_timeout, hot_timeout, config,
            server_url, trade_token, percent, n, k1, k2)
    s.start()

