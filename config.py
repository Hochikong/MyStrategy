#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/1 15:20
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : config.py.py
# @Software: PyCharm

# Year
year = '2018'

# DB
address = 'localhost'
port = 27017
database = 'tradesys'
username = 'tradesystem'
passwd = 'system'

# Scraper
geckopath = 'C:\gecko\geckodriver'
hl_timeout = 5
hot_timeout = 20
# signal_url = http://q.10jqka.com.cn/
# news_url = http://stock.10jqka.com.cn/tzjh_list/
# hot_spot_url = http://yuanchuang.10jqka.com.cn/qingbao/

# TradeServer
server_url = 'http://localhost:5000'
trade_token = ''

# Trade
percent = 0.25
n = 4
k1 = 0.1
k2 = 0.9

# NLP config
config = {
    'boson': [],
    'baidu': [],
    'tencent': []}
