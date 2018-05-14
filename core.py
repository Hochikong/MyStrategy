#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time    : 2018/2/27 22:19
# @Author  : CKHo
# @Email   : ckhoidea@hotmail.com
# @File    : core.py
# @Software: PyCharm

from Strategy.MarketSentiment import *
from stockclib.omServ import mongo_auth_assistant, generate_logger
from Strategy.StockFilter import *
from Strategy.PositionControl import *
from Strategy.RiskControl import *
from functools import reduce
from datetime import datetime
import logging
import requests
import json
import time

# 日志记录
service_status_logger = generate_logger('serv_status', 'runtime/status.log', logging.WARNING)
buy_logger = generate_logger('buyside', 'runtime/buyside.log', logging.INFO)
sell_logger = generate_logger('sellside', 'runtime/sellside.log', logging.INFO)

# 辅助函数
# ---------------------------------------------------------------------------


def log_signal(db, collection, signal):
    """
    在指定的集合里记录此刻信号的变更
    :param db: 指定的数据库对象
    :param collection: 集合名,string,此集合只能存一个文档
    :param signal: dict,e.g. {'signal':'XXX'}
    :return:
    """
    db[collection].insert_one(signal)


def update_stockpool(db, collection, newpool):
    """
    在指定的集合里记录股票池
    :param db: 指定的数据库对象
    :param collection: 集合名,string,此集合只能存一个文档
    :param newpool: list
    :return:
    """
    query = db[collection].find_one()
    if query:
        old = query['pool']
        new = old + newpool
        new = list(set(new))
        db[collection].update_one({'pool': old}, {'$set': {'pool': new}})
    else:
        db[collection].insert_one({'pool': newpool})


def create_bid_order(money, percent, code, today, n, k1, k2):
    """
    根据可支配资金计算每股买percent仓的价格和数量，并返回剩余资金额
    :param money: 可支配资金，float
    :param percent: 比例，比如1/4仓，即0.25,float
    :param code: 股票代码，string
    :param today: 交易日，string
    :param n: DualThrust的n天,int
    :param k1: k1,int.越小越容易出多头信号
    :param k2: k2,int.越大越容易出多头信号
    :return: dict
    """
    df = ts.get_realtime_quotes(code)
    open = float(df['open'][0])
    name = df['name'][0]

    selector = DualThrust(code, today, open, n, k1, k2)

    buy_price = selector.buyline()
    lot_price = buy_price * 100
    if money < lot_price:
        pass
    else:
        remainder = money % lot_price
        amount = ((money - remainder) / lot_price) * 100
        real_amount = amount * percent
        if real_amount % 100 != 0:
            real_amount = int(real_amount - (real_amount % 100))
        remain_money = money - (real_amount * buy_price)
        return {'remain': remain_money,
                'order': {'code': code,
                          'name': name,
                          'ops': 'bid',
                          'amount': str(int(real_amount)),
                          'price': str(buy_price)}
                }


def send_order(orders, url, token):
    """
    把生成的订单集发送到交易服务器
    :param orders: 订单集,list
    :param url: 交易服务器url,string
    :param token: trade token,string
    :return:
    """
    header = {'trade_token': token}
    endpoint = url + "/order"
    order_id = []
    for order in orders:
        payload = json.dumps(order)
        result = requests.post(endpoint, data=payload, headers=header)
        if result.ok:
            order_id.append(result.json()['msg']['order_id'])
    return order_id


def update_stop(db, collection, stops):
    """
    把指定的止盈点率记录到数据库中的指定表中
    :param db: xxx
    :param collection: 储存止盈点的集合
    :param stops: 止盈点集合，list
    :return:
    """
    query = db[collection].find_one()
    if query:
        old = query['stop']
        db[collection].update_one({'stop': old}, {'$set': {'stop': stops}})
    else:
        db[collection].insert_one({'stop': stops})


def target_stop(db, collection, positions):
    """
    根据股票实时收益率计算止盈点
    :param db: 数据库实例
    :param collection: 集合名
    :param positions: 来自交易服务器的仓位信息
    :return: list
    """
    stops = []
    for stat in positions:
        current_rateR = float(stat['rateR'])
        if current_rateR > 0:
            # 判断盈利状况下的止盈点
            if current_rateR > 0.1:
                stop = current_rateR - 0.06
            else:
                if current_rateR > 0.05:
                    stop = current_rateR - 0.04
                elif 0.05 > current_rateR > 0.02:
                    stop = 0.02
                elif 0.02 > current_rateR > 0.0:
                    stop = 1
        else:
            if current_rateR > -0.04:
                # 1代表等待, -1代表即刻抛
                stop = 1
            else:
                stop = -1
        data = {'code': stat['code'], 'stop': round(stop, 3)}
        stops.append(data)

    # 更新止盈点
    update_stop(db, collection, stops)
    # 返回止盈点结果
    return stops

# 下面的为高级功能封装，双方流程的单个功能模块
# ---------------------------------------------------------------------------


def check_market_signal(hl, db, callback):
    """
    检查市场信号并把信号通过回调函数写入数据库
    :param hl: Headless对象
    :param db: 数据库对象
    :param callback: 回调函数，传入数据库对象与文档名用于更新signal到数据库
    :return: string
    """
    rd = fetch_surged_and_decline_data(hl)
    id = fetch_indices_data()
    signal = market_signal_decider(decide_by_surged_and_decline(rd),
                                   decide_by_indices(id))

    now = datetime.now()
    record = {'signal': signal, 'when': now.strftime('%Y-%m-%d %H:%M:%S')}
    callback(db, 'marketsignal', record)
    return signal


def stocks_filter(last_tradingday, today, hot_timeout, market_signal, hl, config, db, callback):
    """
    根据大盘信号决定要不要对当日热点进行挖掘，获取当日热点的股票，并使用均线筛选进行筛选
    :param last_tradingday: 上一个交易日,e.g. '2018-02-27',string
    :param today: 当日，格式和last_tradingday一样,string
    :param market_signal: check_market_signal
    :param hl: Headless对象
    :param config: judges函数的config参数
    :param db: 数据库实例
    :param callback: 回调函数，使用update_stockpool函数
    :return: list
    """
    if market_signal == 'N':
        pass
    if market_signal == 'P':
        # 基于热点筛选的股票
        hot = HotSpot(today, hot_timeout)
        urls = hot.get_today_hotspot_urls(hl.browser)
        tmp = []
        for url in urls:
            tmp.append(hot.get_today_hotspot(url, hl.browser))
        after_filter = [general_ma_filterv2(4, pot, last_tradingday) for pot in tmp]

        # 基于新闻筛选
        # after_gmf = []
        # before_gmf = codes_from_positive_news(today, config)
        # for unit in before_gmf:
        #     after_gmf.append(general_ma_filterv2(4, unit, last_tradingday))

        # 生成股票池
        # total = after_filter+after_gmf
        total = after_filter
        stock_pool = []
        for code_list in total:
            for code in code_list:
                stock_pool.append(code)
        stock_pool = list(set(stock_pool))
        callback(db, 'stockpool', stock_pool)

        return after_filter


def positions(url, token):
    """
    根据用户的总收益率决定可用资金额度以及可支配资金的计算
    :param url: 交易服务器
    :param token: 用户的trade token
    :return:
    """
    user_account_info = get_accounti(url, token)
    # 获取总收益率
    profit_rate = float(user_account_info['profit'][0]['stat'][0]['AllrateR'])
    # 获取所有持仓股票
    if 'stocks_rateR' not in list(user_account_info['profit'][0].keys()):
        # 无持仓情况下
        all_money = float(user_account_info['balance']['balance'])

        # 收益为0时
        if profit_rate == 0.0:
            money_for_trading = all_money * 0.5
            return money_for_trading
        # 收益不为0时
        else:
            if profit_rate > 0:
                if profit_rate > 0.08:
                    if profit_rate > 0.15:
                        money_for_trading = all_money
                    else:
                        money_for_trading = all_money * 0.75
                else:
                    money_for_trading = all_money * 0.5
            else:
                if profit_rate < -0.03:
                    money_for_trading = all_money * 0.5
                else:
                    money_for_trading = all_money * 0.25

            return money_for_trading

    # 有持仓的情况下
    else:
        stocks_record = user_account_info['profit'][0]['stocks_rateR']
        total_cost = [float(record['avgprice']) * float(record['amount']) for record in stocks_record]
        # 计算持仓股票的总成本
        total_cost = reduce(lambda x, y: x + y, total_cost)
        # 根据余额与持仓总成本计算总资金量
        all_money = total_cost + float(user_account_info['balance']['balance'])

        # 根据总收益率计算可用资金
        if profit_rate > 0:
            if profit_rate > 0.08:
                if profit_rate > 0.15:
                    money_for_use = all_money
                else:
                    money_for_use = all_money * 0.75
            else:
                money_for_use = all_money * 0.5
        else:
            if profit_rate < -0.03:
                money_for_use = all_money * 0.5
            else:
                money_for_use = all_money * 0.25

        # 计算可支配资金
        if total_cost < money_for_use:
            money_for_trading = money_for_use - total_cost
        else:
            money_for_trading = 0
        return money_for_trading


def bid(codes, money, percent, today, n, k1, k2, url, token):
    """
    根据可支配资金生成订单
    :param codes: 股票代码集合，list
    :param money: 可支配资金，float
    :param percent: 比例，比如1/4仓，即0.25,float
    :param today: 交易日，string，e.g. '2018-02-28'
    :param n: DualThrust的n天,int
    :param k1: k1,int.越小越容易出多头信号
    :param k2: k2,int.越大越容易出多头信号
    :param url: 交易服务器url,string
    :param token: trade token,string
    :return:
    """
    min_row_length = len(min(codes, key=len))
    if min_row_length >= 1:
        what_i_buy = []
        for line in codes:
            what_i_buy.append(line[0])

        orders = []
        current_money = money
        remain_orders = get_orders(url, token)['msg']['remain_orders']
        remain_order_codes = [i['code'] for i in remain_orders if i['ops'] == 'bid']
        if len(remain_orders) > 0:
            # 防止生成重复订单
            what_i_buy = [code for code in what_i_buy if code not in remain_order_codes]
        for code in what_i_buy:
            result = create_bid_order(current_money, percent, code, today, n, k1, k2)
            if result is not None:
                orders.append(result['order'])
                current_money = result['remain']
        order_id = send_order(orders, url, token)
        return order_id
    else:
        pass


def offer(stops, url, token):
    """
    根据止盈点数据检查是否要平仓
    :param stops:
    :param url:
    :param token:
    :return:
    """
    current_stat = get_return_rate(url, token)[0].get('stocks_rateR')
    if current_stat:
        offer_orders = []
        for index, element in enumerate(stops):
            # 如果stop值为1，等待回升
            if stops[index]['stop'] == 1:
                continue
            # 如果实时收益率等于/低于止盈点,或者stop值为-1，生成卖单平仓
            if stops[index]['stop'] == -1 or float(current_stat[index]['rateR']) <= stops[index]['stop']:
                ele = current_stat[index]
                name = ts.get_realtime_quotes(ele['code'])['name'][0]
                offer_orders.append({'code': ele['code'],
                                     'name': name,
                                     'ops': 'offer',
                                     'amount': ele['amount'],
                                     'price': ele['current_price']})
        # 防止生成重复卖单
        remain_orders = get_orders(url, token)['msg']['remain_orders']
        remain_order_codes = [i['code'] for i in remain_orders if i['ops'] == 'offer']
        offer_orders = [o for o in offer_orders if o['code'] not in remain_order_codes]

        if len(offer_orders) > 0:
            order_id = send_order(offer_orders, url, token)
            return order_id
        else:
            pass
    else:
        pass


def risk(url, token, db, collection):
    """
    计算止盈点
    :param url:
    :param token:
    :param db:
    :param collection: 用于储存stops的文档
    :return:
    """
    stat = get_return_rate(url, token)
    if 'stocks_rateR' in list(stat[0].keys()):
        all_positions = stat[0]['stocks_rateR']
        stops = target_stop(db, collection, all_positions)
        return stops
    else:
        return 'No position'

# 下面为买卖双方的逻辑封装，使用多进程执行双方逻辑
# ---------------------------------------------------------------------------


def buyside_wrapper(status, hl, db, cms_callback, ltday, today, hot_timeout, nlp_config,
                    us_callback, server_url, trade_token, percent, n, k1, k2):
    """
    包装了买方决策流程
    :param status
    :param hl:
    :param db:
    :param cms_callback:
    :param ltday:
    :param today:
    :param hot_timeout:
    :param nlp_config:
    :param us_callback:
    :param server_url:
    :param trade_token:
    :param percent:
    :param n:
    :param k1:
    :param k2:
    :return:
    """
    if status == 'run':
        signal = check_market_signal(hl, db, cms_callback)
        buy_logger.info('Current signal: {0}'.format(signal))
        if signal == 'P':
            # 从热点获取股票代码，并生成股票池写入数据库
            wait_for_buy = stocks_filter(ltday, today, hot_timeout, signal, hl, nlp_config, db, us_callback)
            wait_for_buy = [l[0] for l in wait_for_buy if len(l) > 0]
            position_codes = []
            positions_info = get_return_rate(server_url, trade_token)[0]
            if 'stocks_rateR' in list(positions_info.keys()):
                for p in positions_info['stocks_rateR']:
                    position_codes.append(p['code'])

            # 从待买池里去掉已经持仓的股票
            for p in position_codes:
                if p in wait_for_buy:
                    wait_for_buy.remove(p)
            if len(wait_for_buy) > 0:
                buy_logger.info('Ready for bid: {0}'.format(wait_for_buy))
                # 修改数据格式
                wait_for_buy = [[c] for c in wait_for_buy]
                # 计算可支配资金
                money = positions(server_url, trade_token)
                buy_logger.info('Allocate money: {0}'.format(money))
                # 如果发送订单成果，result是订单ID的列表
                result = bid(wait_for_buy, money, percent, today, n, k1, k2, server_url, trade_token)
                buy_logger.info('Order ID: {0}'.format(result))
                return result
            else:
                pass
    else:
        time.sleep(5)


def sellside_wrapper(status, server_url, trade_token, db):
    """
    包装了卖方决策流程
    :param status:
    :param server_url:
    :param trade_token:
    :param db:
    :return:
    """
    if status == 'run':
        query = db['stops'].find_one()
        if query:
            old_stops = query['stop']
            position = get_return_rate(server_url, trade_token)[0].get('stocks_rateR', None)
            if isinstance(old_stops, list):
                # 查询止盈点生成卖单再生成新的止盈点
                if position is not None:
                    codes_from_position = [i['code'] for i in position]
                    # 避免抛掉某只股票后还剩余旧的stop导致错误
                    clean_old_stops = [i for i in old_stops if i['code'] in codes_from_position]
                    result = offer(clean_old_stops, server_url, trade_token)
                    sell_logger.info('Order ID: {0}'.format(result))
                    new_stops = risk(server_url, trade_token, db, 'stops')
                    sell_logger.info('Stops: {0}'.format(new_stops))
                    return result
                else:
                    # 无持仓
                    pass
        # 如果有持仓但尚未记录止盈点的话就进入这个逻辑
        else:
            stops = risk(server_url, trade_token, db, 'stops')
            sell_logger.info('Stops: {0}'.format(stops))

    else:
        time.sleep(5)


def check_status(current_status, db):
    """
    检查数据库的信号状态，以决定策略是否运行，trading_run集合里status要设置为run策略才会运行
    :param current_status:
    :param db:
    :return:
    """
    status = db['trading_run'].find_one()['status']
    # 没有变更信号的话就返回原信号
    if current_status == status:
        return current_status
    else:
        service_status_logger.warning('Current status: %s' % status)
        return status


class Buy(object):
    def __init__(self, address, port, username, passwd, database,
                 geckopath, hl_timeout, hot_timeout, config, server_url, trade_token, percent, n, k1, k2):
        self.status = 'stop'
        self.db = mongo_auth_assistant(address, port, username, passwd, database)[database]
        self.hl = Headless(geckopath, hl_timeout)
        self.hot_timeout = hot_timeout
        self.config = config
        self.all_open = self.db['trading_days'].find_one()['open']
        self.server_url = server_url
        self.trade_token = trade_token
        self.percent = percent
        self.nday = n
        self.k1 = k1
        self.k2 = k2

        # 日期参数
        self.today = datetime.now()
        self.day = self.today.strftime('%Y-%m-%d')
        self.last_trading_day = self.all_open[self.all_open.index(self.day)-1]
        self.now = self.today.strftime('%H:%M:%S')

    def start(self):
        while True:
            result = check_status(self.status, self.db)
            self.status = result
            buyside_wrapper(self.status, self.hl, self.db, log_signal, self.last_trading_day, self.day,
                            self.hot_timeout, self.config, update_stockpool, self.server_url, self.trade_token,
                            self.percent, self.nday, self.k1, self.k2)
            time.sleep(1800)


class Sell(Buy):
    def __init__(self,address, port, username, passwd, database,
                 geckopath, hl_timeout, hot_timeout, config, server_url, trade_token, percent, n, k1, k2):
        super(Sell, self).__init__(address, port, username, passwd, database,
                                   geckopath, hl_timeout, hot_timeout, config, server_url,
                                   trade_token, percent, n, k1, k2)

    def start(self):
        while True:
            result = check_status(self.status, self.db)
            self.status = result
            sellside_wrapper(self.status, self.server_url, self.trade_token, self.db)
            time.sleep(120)
