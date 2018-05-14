#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/2 10:09
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : sells.py
# @Software: PyCharm

from core import Sell
from config import *
import os

if __name__ == "__main__":
    file = open('runtime/sellside.pid', 'w')
    file.write(str(os.getpid()))
    file.close()
    s = Sell(address, port, username, passwd, database,
            geckopath, hl_timeout, hot_timeout, config,
            server_url, trade_token, percent, n, k1, k2)
    s.start()