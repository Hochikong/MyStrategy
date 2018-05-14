#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/3/7 10:50
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : cancelorders.py
# @Software: PyCharm

# 本程序用于手动清除没有成交的订单

from config import *
import requests
import json

endpoint = server_url + '/order'
header = {'trade_token': trade_token}

cancel = {"ops": "cancel", "order_id": None}

if __name__ == '__main__':
    result = requests.get(endpoint, headers=header)
    result = result.json()
    remain_orders = result['msg']['remain_orders']

    # 找出尚未成交的订单id
    order_ids = []
    if len(remain_orders) > 0:
        for o in remain_orders:
            order_ids.append(o['order_id'])

        # 发出撤单请求
        for oid in order_ids:
            cancel['order_id'] = oid
            payload = json.dumps(cancel)
            requests.post(endpoint, headers=header, data=payload)

        print('Cancel all orders done')
    else:
        print('No remain orders')
