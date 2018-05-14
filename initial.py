#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/1 15:19
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : initial.py
# @Software: PyCharm

from Strategy.UniversalMethod import all_trading_day
from stockclib.omServ import mongo_auth_assistant
from config import *

db = mongo_auth_assistant(address, port, username, passwd, database)[database]
data = all_trading_day(year)

if __name__ == "__main__":
    # 记录今年的所有交易日数据
    db['trading_days'].insert_one({'open': data})
    db['trading_run'].insert_one({'status': 'run'})
    print('Done')