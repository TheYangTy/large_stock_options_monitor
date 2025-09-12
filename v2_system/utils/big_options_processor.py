# -*- coding: utf-8 -*-
"""
V2系统大单期权处理器 - 独立版本
"""

import json
import os
import logging
import pandas as pd
import time
import traceback
import re
import functools
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, TypeVar, ParamSpec
import sys

# 添加V2系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BIG_TRADE_CONFIG, TRADING_HOURS, OPTION_FILTERS, SYSTEM_CONFIG
import futu as ft


P = ParamSpec("P")
R = TypeVar("R")

def retry_on_api_error(max_retries: int = 3, *, delay: float = 5.0) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """API调用失败时的重试装饰器，默认重试间隔5秒"""
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            logger = logging.getLogger('V2OptionMonitor.BigOptionsProcessor')
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"API调用失败，已重试{retries}次，放弃: {e}")
                        raise
                    logger.warning(f"API调用失败，{retries}/{max_retries}次重试: {e}")
                    time.sleep(delay)  # 使用可配置的重试间隔
                    logger.info(f"正在进行第{retries}次重试...")
            # 理论上不会到这里；为安全起见最后再尝试一次
            return func(*args, **kwargs)
        return wrapper
    return decorator


class BigOptionsProcessor:
    """V2系统大单期权处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger('V2OptionMonitor.BigOptionsProcessor')
        self.json_file = os.path.join(SYSTEM_CONFIG['cache_dir'], 'big_options_v2.json')
        self.stock_price_cache = {}  # 缓存股价信息
        self.price_cache_time = {}   # 缓存时间
        self.last_option_volumes = {}  # 缓存上一次的期权交易量
        self.notification_history = {}  # 通知历史，避免重复通知
        self.today_option_volumes = {}  # 当日期权成交量缓存
        self.today_volumes_loaded = False  # 是否已加载当日数据
        
        # 确保缓存目录存在
        os.makedirs(os.path.dirname(self.json_file), exist_ok=True)
    
    def _load_today_option_volumes(self) -> Dict[str, int]:
        """从数据库/文件加载当日期权成交量"""
        if self.today_volumes_loaded:
            return self.today_option_volumes
        
        try:
            from .data_handler import V2DataHandler
            data_handler = V2DataHandler()
            
            # 加载当日期权数据
            today = datetime.now().strftime('%Y-%m-%d')
            today_data = []
            
            # 尝试加载当日数据文件
            cache_dir = SYSTEM_CONFIG['cache_dir']
            today_file = os.path.join(cache_dir, f'options_{today}.json')
            
            if os.path.exists(today_file):
                try:
                    with open(today_file, 'r', encoding='utf-8') as f:
                        today_data = json.load(f)
                    self.logger.info(f"V2加载当日期权数据: {len(today_data)}条记录")
                except Exception as e:
                    self.logger.warning(f"V2加载当日期权数据失败: {e}")
            
            # 构建期权代码到最新成交量的映射
            option_volumes = {}
            for record in today_data:
                option_code = record.get('option_code')
                volume = record.get('volume', 0)
                timestamp = record.get('timestamp', '')
                
                if option_code:
                    # 保留最新的成交量记录
                    if option_code not in option_volumes or timestamp > option_volumes[option_code]['timestamp']:
                        option_volumes[option_code] = {
                            'volume': int(volume),
                            'timestamp': timestamp
                        }
            
            # 提取成交量
            self.today_option_volumes = {
                code: data['volume'] for code, data in option_volumes.items()
            }
            
            self.today_volumes_loaded = True
            self.logger.info(f"V2加载当日期权成交量: {len(self.today_option_volumes)}个期权")
            
            return self.today_option_volumes
            
        except Exception as e:
            self.logger.error(f"V2加载当日期权成交量失败: {e}")
            return {}
    
    def _get_last_recorded_volume(self, option_code: str) -> int:
        """获取数据库中最后记录的期权成交量"""
        try:
            # 确保已加载当日数据
            today_volumes = self._load_today_option_volumes()
            
            # 返回当日最后记录的成交量，如果没有记录则返回0
            return today_volumes.get(option_code, 0)
            
        except Exception as e:
            self.logger.debug(f"V2获取{option_code}最后记录成交量失败: {e}")
            return 0
    
    def _update_today_volume_cache(self, option_code: str, volume: int):
        """更新当日成交量缓存"""
        try:
            # 确保已加载当日数据
            if not self.today_volumes_loaded:
                self._load_today_option_volumes()
            
            # 更新缓存
            self.today_option_volumes[option_code] = volume
            
        except Exception as e:
            self.logger.debug(f"V2更新{option_code}成交量缓存失败: {e}")
    
    def _load_stock_info_from_file(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """从V2系统文件读取单只股票信息"""
        try:
            prices_file = SYSTEM_CONFIG['price_cache']
            base_file = SYSTEM_CONFIG['stock_info_cache']

            price_val = None
            name_val = ""

            # 先尝试基础信息中的名称
            try:
                if os.path.exists(base_file):
                    with open(base_file, 'r', encoding='utf-8') as f:
                        base_data = json.load(f)
                    stocks = base_data.get('stocks') if isinstance(base_data, dict) else None
                    if isinstance(stocks, dict):
                        base_info = stocks.get(stock_code)
                        if isinstance(base_info, dict):
                            n = base_info.get('name')
                            if isinstance(n, str) and n.strip():
                                name_val = n
            except Exception:
                pass

            # 读取价格与（次级）名称
            if os.path.exists(prices_file):
                with open(prices_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                info = (data.get('prices') or {}).get(stock_code)
                if isinstance(info, dict):
                    pv = info.get('price')
                    if isinstance(pv, (int, float)):
                        price_val = float(pv)
                    # 若基础信息没有名称，则尝试从这里补充
                    n2 = info.get('name')
                    if (not name_val) and isinstance(n2, str) and n2.strip():
                        name_val = n2

            if isinstance(price_val, (int, float)):
                return {'price': float(price_val), 'name': name_val}
            return None
        except Exception:
            return None

    def get_recent_big_options(self, quote_ctx, stock_codes: List[str], option_monitor=None) -> List[Dict[str, Any]]:
        """获取最近的大单期权 - V2版本"""
        all_big_options = []
        processed_stocks = set()
        failed_stocks = set()
        
        self.logger.info(f"V2系统开始获取 {len(stock_codes)} 只股票的大单期权数据...")
        
        # 预先获取所有股票的价格
        stock_prices = self._batch_get_stock_prices(quote_ctx, stock_codes, option_monitor)
        
        for i, stock_code in enumerate(stock_codes):
            try:
                if stock_code in processed_stocks or stock_code in failed_stocks:
                    continue
                
                self.logger.info(f"V2处理 {i+1}/{len(stock_codes)}: {stock_code}")
                
                # 获取该股票的所有期权代码
                try:
                    option_codes = self._get_option_codes(quote_ctx, stock_code, option_monitor)
                except Exception as e:
                    self.logger.error(f"V2获取{stock_code}期权代码异常: {e}")
                    failed_stocks.add(stock_code)
                    continue
                
                if option_codes:
                    self.logger.info(f"V2 {stock_code} 获取到 {len(option_codes)} 个期权代码")
                    
                    # 处理所有期权
                    stock_big_options = []
                    error_count = 0
                    
                    for j, option_code in enumerate(option_codes):
                        try:
                            if error_count >= 3:
                                self.logger.warning(f"V2连续错误超过3次，跳过{stock_code}剩余期权")
                                break
                                
                            option_big_trades = self._get_option_big_trades(quote_ctx, option_code, stock_code, option_monitor)
                            if option_big_trades:
                                # 检查是否需要通知
                                for trade in option_big_trades:
                                    if self._should_notify(trade):
                                        stock_big_options.append(trade)
                                        self.logger.info(f"V2期权 {j+1}/{len(option_codes)}: {option_code} 发现 {len(option_big_trades)} 笔大单")
                                error_count = 0
                            
                            # 每处理5个期权暂停一下
                            if (j + 1) % 5 == 0:
                                time.sleep(0.5)
                                
                        except Exception as e:
                            self.logger.error(f"V2处理期权 {option_code} 失败: {e}")
                            error_count += 1
                    
                    if stock_big_options:
                        self.logger.info(f"V2 {stock_code} 发现 {len(stock_big_options)} 笔大单期权")
                        all_big_options.extend(stock_big_options)
                    else:
                        self.logger.info(f"V2 {stock_code} 未发现大单期权")
                else:
                    self.logger.warning(f"V2 {stock_code} 未获取到期权代码")
                
                processed_stocks.add(stock_code)
                time.sleep(1)  # 避免API调用过于频繁
                
            except Exception as e:
                self.logger.error(f"V2获取{stock_code}大单期权失败: {e}")
                self.logger.error(traceback.format_exc())
        
        # 按成交额降序排序
        all_big_options.sort(key=lambda x: x.get('turnover', 0), reverse=True)
        
        # 为每个期权添加正股价格和名称信息
        for option in all_big_options:
            stock_code = option.get('stock_code')
            if stock_code and stock_code in stock_prices:
                stock_info = stock_prices[stock_code]
                if isinstance(stock_info, dict):
                    option['stock_price'] = stock_info.get('price', 0)
                    option['stock_name'] = stock_info.get('name', '')
                else:
                    option['stock_price'] = stock_info
        
        self.logger.info(f"V2系统总共发现 {len(all_big_options)} 笔大单期权")
        
        # 打印每只股票的大单数量
        stock_counts = {}
        for option in all_big_options:
            stock_code = option.get('stock_code', 'Unknown')
            stock_counts[stock_code] = stock_counts.get(stock_code, 0) + 1
        
        for stock_code, count in stock_counts.items():
            self.logger.info(f"📊 V2 {stock_code}: {count} 笔大单")
        
        return all_big_options
    
    def _should_notify(self, trade_info: Dict[str, Any]) -> bool:
        """检查是否应该发送通知（避免重复通知）"""
        option_code = trade_info.get('option_code')
        current_time = datetime.now()
        
        # 检查通知冷却时间
        if option_code in self.notification_history:
            last_notify_time = self.notification_history[option_code]
            if (current_time - last_notify_time).seconds < BIG_TRADE_CONFIG['notification_cooldown']:
                return False
        
        # 检查是否满足大单条件
        volume = trade_info.get('volume', 0)
        turnover = trade_info.get('turnover', 0)
        
        if (volume >= BIG_TRADE_CONFIG['min_volume_threshold'] and 
            turnover >= BIG_TRADE_CONFIG['min_turnover_threshold']):
            
            # 更新通知历史
            self.notification_history[option_code] = current_time
            return True
        
        return False
    
    @retry_on_api_error(max_retries=3)
    def _batch_get_stock_prices(self, quote_ctx, stock_codes: List[str], option_monitor=None) -> Dict[str, Dict[str, Any]]:
        """V2系统批量获取股票价格和名称"""
        result = {}
        current_time = datetime.now()
        
        # 如果提供了option_monitor实例，优先使用其股价缓存
        if option_monitor and hasattr(option_monitor, 'stock_price_cache'):
            self.logger.info(f"V2使用option_monitor中的股价缓存")
            
            for stock_code in stock_codes:
                if stock_code in option_monitor.stock_price_cache:
                    price_obj = option_monitor.stock_price_cache[stock_code]

                    actual_price = None
                    name_from_monitor = ""
                    if isinstance(price_obj, dict):
                        try:
                            pv = price_obj.get('price')
                            if isinstance(pv, (int, float)):
                                actual_price = float(pv)
                            name_from_monitor = price_obj.get('name', '') or ""
                        except Exception:
                            actual_price = None
                    else:
                        if isinstance(price_obj, (int, float)):
                            actual_price = float(price_obj)

                    stock_info = {
                        'price': float(actual_price) if isinstance(actual_price, (int, float)) else 0.0,
                        'name': name_from_monitor
                    }

                    # 如果没有名称，尝试从文件缓存补齐
                    if not stock_info['name']:
                        file_info = self._load_stock_info_from_file(stock_code)
                        if file_info and file_info.get('name'):
                            stock_info['name'] = file_info['name']

                    result[stock_code] = stock_info
                    self.stock_price_cache[stock_code] = stock_info
                    self.price_cache_time[stock_code] = current_time
                    self.logger.debug(f"V2从option_monitor获取股价: {stock_code} = {stock_info['price']}")
                else:
                    # 检查本地缓存
                    if stock_code in self.stock_price_cache and stock_code in self.price_cache_time:
                        if (current_time - self.price_cache_time[stock_code]).seconds < 300:
                            result[stock_code] = self.stock_price_cache[stock_code]
                            continue
        else:
            # 检查哪些股票需要更新价格
            for stock_code in stock_codes:
                if stock_code in self.stock_price_cache and stock_code in self.price_cache_time:
                    if (current_time - self.price_cache_time[stock_code]).seconds < 300:
                        result[stock_code] = self.stock_price_cache[stock_code]
                        continue
        
        # 找出仍需要更新的股票
        stocks_to_update = [code for code in stock_codes if code not in result]
        
        if not stocks_to_update:
            self.logger.info("V2所有股价都已获取，无需更新")
            return result
        
        # 批量获取股价和名称
        try:
            self.logger.info(f"V2批量获取 {len(stocks_to_update)} 只股票的价格和名称...")
            ret, data = quote_ctx.get_market_snapshot(stocks_to_update)
            
            if ret == ft.RET_OK and not data.empty:
                for _, row in data.iterrows():
                    code = row['code']
                    price = float(row['last_price'])
                    name = row.get('name', '') or row.get('stock_name', '')
                    
                    stock_info = {
                        'price': price,
                        'name': name
                    }
                    
                    result[code] = stock_info
                    self.stock_price_cache[code] = stock_info
                    self.price_cache_time[code] = current_time
                    self.logger.debug(f"V2获取股票信息: {code} = {price} ({name})")
                
                self.logger.info(f"V2成功获取 {len(data)} 只股票的价格和名称")
            else:
                self.logger.warning(f"V2批量获取股票信息失败: {ret}")
                # 使用缓存中的旧数据
                for stock_code in stocks_to_update:
                    if stock_code in self.stock_price_cache:
                        result[stock_code] = self.stock_price_cache[stock_code]
        
        except Exception as e:
            self.logger.error(f"V2批量获取股票信息异常: {e}")
            # 使用缓存中的旧数据
            for stock_code in stocks_to_update:
                if stock_code in self.stock_price_cache:
                    result[stock_code] = self.stock_price_cache[stock_code]
        
        return result
    
    @retry_on_api_error(max_retries=3)
    def get_stock_price(self, quote_ctx, stock_code: str, option_monitor=None) -> Dict[str, Any]:
        """V2系统获取股票当前价格和名称（带缓存）"""
        try:
            current_time = datetime.now()
            
            # 如果提供了option_monitor实例，优先使用其股价缓存
            if option_monitor and hasattr(option_monitor, 'stock_price_cache') and stock_code in option_monitor.stock_price_cache:
                price = option_monitor.stock_price_cache[stock_code]
                
                stock_info = {
                    'price': price,
                    'name': ''
                }
                
                # 如果本地缓存中有名称信息，补充名称
                if stock_code in self.stock_price_cache and isinstance(self.stock_price_cache[stock_code], dict):
                    old_info = self.stock_price_cache[stock_code]
                    if 'name' in old_info and old_info['name']:
                        stock_info['name'] = old_info['name']
                
                # 更新本地缓存
                self.stock_price_cache[stock_code] = stock_info
                self.price_cache_time[stock_code] = current_time
                self.logger.debug(f"V2从option_monitor获取股价: {stock_code} = {price}")
                
                return stock_info
            
            # 检查本地缓存
            if (stock_code in self.stock_price_cache and 
                stock_code in self.price_cache_time and
                (current_time - self.price_cache_time[stock_code]).seconds < 300):
                
                stock_info = self.stock_price_cache[stock_code]
                if isinstance(stock_info, dict):
                    self.logger.debug(f"V2使用缓存的股票信息: {stock_code} = {stock_info['price']} ({stock_info['name']})")
                else:
                    # 兼容旧格式
                    stock_info = {'price': stock_info, 'name': ''}
                    self.stock_price_cache[stock_code] = stock_info
                
                return stock_info
            
            # 获取实时股票信息
            ret, snap_data = quote_ctx.get_market_snapshot([stock_code])
            if ret == ft.RET_OK and not snap_data.empty:
                row = snap_data.iloc[0]
                price = float(row['last_price'])
                name = row.get('name', '') or row.get('stock_name', '')
                
                stock_info = {'price': price, 'name': name}
                self.stock_price_cache[stock_code] = stock_info
                self.price_cache_time[stock_code] = current_time
                self.logger.debug(f"V2获取股票信息: {stock_code} = {price} ({name})")
                
                # 如果提供了option_monitor实例，同时更新其缓存
                if option_monitor and hasattr(option_monitor, 'stock_price_cache'):
                    option_monitor.stock_price_cache[stock_code] = price
                    if hasattr(option_monitor, 'price_update_time'):
                        option_monitor.price_update_time[stock_code] = current_time
                
                return stock_info
            else:
                # 使用默认股票信息
                default_stocks = {
                    'HK.00700': {'price': 600.0, 'name': '腾讯控股'},
                    'HK.09988': {'price': 80.0, 'name': '阿里巴巴-SW'},
                    'HK.03690': {'price': 120.0, 'name': '美团-W'},
                    'HK.01810': {'price': 12.0, 'name': '小米集团-W'},
                    'HK.09618': {'price': 120.0, 'name': '京东集团-SW'},
                    'HK.02318': {'price': 40.0, 'name': '中国平安'},
                    'HK.00388': {'price': 300.0, 'name': '香港交易所'},
                }
                
                if stock_code in default_stocks:
                    stock_info = default_stocks[stock_code]
                    self.logger.info(f"V2使用默认股票信息: {stock_code} = {stock_info['price']} ({stock_info['name']})")
                    self.stock_price_cache[stock_code] = stock_info
                    self.price_cache_time[stock_code] = current_time
                    return stock_info
                
                return {'price': 0.0, 'name': ''}
        except Exception as e:
            self.logger.error(f"V2获取{stock_code}股票信息异常: {e}")
            
            # 如果缓存中有旧数据，返回旧数据
            if stock_code in self.stock_price_cache:
                return self.stock_price_cache[stock_code]
            
            # 使用默认股票信息
            default_stocks = {
                'HK.00700': {'price': 600.0, 'name': '腾讯控股'},
                'HK.09988': {'price': 134.4, 'name': '阿里巴巴-SW'},
                'HK.03690': {'price': 120.0, 'name': '美团-W'},
                'HK.01810': {'price': 12.0, 'name': '小米集团-W'},
                'HK.09618': {'price': 120.0, 'name': '京东集团-SW'},
                'HK.02318': {'price': 40.0, 'name': '中国平安'},
                'HK.00388': {'price': 300.0, 'name': '香港交易所'},
            }
            
            if stock_code in default_stocks:
                stock_info = default_stocks[stock_code]
                self.logger.info(f"V2异常时使用默认股票信息: {stock_code} = {stock_info['price']} ({stock_info['name']})")
                return stock_info
                
            return {'price': 0.0, 'name': ''}
    
    @retry_on_api_error(max_retries=3)
    def _get_option_codes(self, quote_ctx, stock_code: str, option_monitor=None) -> List[str]:
        """V2系统获取期权代码列表"""
        try:
            option_codes = []
            
            # 获取当前股价
            try:
                current_price = None
                
                if option_monitor is not None:
                    stock_info = option_monitor.get_stock_price(stock_code)
                    if isinstance(stock_info, (int, float)):
                        current_price = float(stock_info)
                        self.logger.info(f"V2 {stock_code}当前股价(来自缓存): {current_price}")
                    elif isinstance(stock_info, dict) and stock_info.get('price'):
                        current_price = float(stock_info['price'])
                        self.logger.info(f"V2 {stock_code}当前股价(来自缓存): {current_price}")
                
                if current_price is None or current_price <= 0:
                    file_info = self._load_stock_info_from_file(stock_code)
                    if file_info and file_info.get('price'):
                        current_price = float(file_info['price'])
                        self.logger.info(f"V2 {stock_code}当前股价(来自文件缓存): {current_price}")
                    else:
                        # 使用默认价格
                        default_prices = {
                            'HK.00700': 600.0, 'HK.09988': 80.0, 'HK.03690': 120.0,
                            'HK.01810': 15.0, 'HK.09618': 120.0, 'HK.02318': 40.0,
                            'HK.00388': 300.0
                        }
                        current_price = default_prices.get(stock_code, 100.0)
                        self.logger.info(f"V2 {stock_code}当前股价(使用默认价格): {current_price}")
                
                # 基于股价设定期权执行价格过滤范围
                price_range = OPTION_FILTERS['default'].get('price_range', 0.2)
                price_lower = current_price * (1 - price_range)
                price_upper = current_price * (1 + price_range)
                self.logger.info(f"V2筛选价格范围: {price_lower:.2f} - {price_upper:.2f} (±{price_range*100}%)")
            except Exception as e:
                self.logger.error(f"V2获取{stock_code}当前股价失败: {e}")
                current_price = 100.0
                price_range = 0.5
                price_lower = current_price * (1 - price_range)
                price_upper = current_price * (1 + price_range)
            
            # 获取期权到期日
            try:
                ret, expiry_data = quote_ctx.get_option_expiration_date(stock_code)
                if ret != ft.RET_OK or expiry_data.empty:
                    self.logger.warning(f"V2 {stock_code}没有期权合约或API调用失败")
                    return []
                
                # 只获取最近1个月内的期权链
                now = datetime.now()
                one_month_later = now + timedelta(days=30)
                
                valid_dates = []
                for _, row in expiry_data.iterrows():
                    expiry = row['strike_time']
                    if isinstance(expiry, str):
                        try:
                            expiry = datetime.strptime(expiry, '%Y-%m-%d')
                        except:
                            continue
                    
                    if isinstance(expiry, pd.Timestamp):
                        expiry = expiry.to_pydatetime()
                    
                    if now <= expiry <= one_month_later:
                        valid_dates.append(row)
                
                recent_dates = pd.DataFrame(valid_dates) if valid_dates else expiry_data.head(2)
                self.logger.info(f"V2 {stock_code} 找到 {len(expiry_data)} 个到期日，筛选出 {len(recent_dates)} 个1个月内的到期日")
                
                for _, row in recent_dates.iterrows():
                    try:
                        expiry_date = row['strike_time']
                        
                        date_str = expiry_date
                        if isinstance(expiry_date, pd.Timestamp):
                            date_str = expiry_date.strftime('%Y-%m-%d')
                        elif isinstance(expiry_date, datetime):
                            date_str = expiry_date.strftime('%Y-%m-%d')
                        
                        self.logger.debug(f"V2获取 {stock_code} {date_str} 的期权链")
                        ret2, option_data = quote_ctx.get_option_chain(
                            code=stock_code, 
                            start=date_str, 
                            end=date_str,
                            option_type=ft.OptionType.ALL,
                            option_cond_type=ft.OptionCondType.ALL
                        )
                                
                        if ret2 == ft.RET_OK and not option_data.empty:
                            self.logger.info(f"V2 API调用成功: {stock_code} {expiry_date}, 获取到 {len(option_data)} 个期权")
                        else:
                            self.logger.warning(f"V2 API调用返回空数据: {stock_code} {expiry_date}")
                        
                        time.sleep(0.5)  # 避免API限流
                        
                        if ret2 == ft.RET_OK and not option_data.empty:
                            # 筛选执行价格在当前股价上下范围内的期权
                            filtered_options = option_data[
                                (option_data['strike_price'] >= price_lower) & 
                                (option_data['strike_price'] <= price_upper)
                            ]
                            
                            if not filtered_options.empty:
                                option_codes.extend(filtered_options['code'].tolist())
                                self.logger.info(f"V2 {stock_code} {expiry_date}到期的期权中有{len(filtered_options)}个在价格范围内")
                            else:
                                # 如果没有在范围内的期权，尝试放宽范围
                                wider_range = price_range * 1.5
                                wider_lower = current_price * (1 - wider_range)
                                wider_upper = current_price * (1 + wider_range)
                                
                                wider_filtered = option_data[
                                    (option_data['strike_price'] >= wider_lower) & 
                                    (option_data['strike_price'] <= wider_upper)
                                ]
                                
                                if not wider_filtered.empty:
                                    wider_filtered = wider_filtered.copy()
                                    wider_filtered.loc[:, 'price_diff'] = abs(wider_filtered['strike_price'] - current_price)
                                    closest_options = wider_filtered.nsmallest(5, 'price_diff')
                                    option_codes.extend(closest_options['code'].tolist())
                                    self.logger.info(f"V2使用更宽范围添加 {len(closest_options)} 个最接近当前价格的期权")
                    except Exception as e:
                        self.logger.warning(f"V2获取{stock_code}期权链失败: {e}")
                        continue
                
            except Exception as e:
                self.logger.error(f"V2获取{stock_code}期权到期日失败: {e}")
                return []
            
            if option_codes:
                self.logger.info(f"V2 {stock_code}获取到{len(option_codes)}个期权合约")
            else:
                self.logger.error(f"V2 {stock_code}未找到期权合约")
            
            return option_codes
            
        except Exception as e:
            self.logger.error(f"V2获取{stock_code}期权代码失败: {e}")
            return []
    
    @retry_on_api_error(max_retries=3)
    def _get_option_big_trades(self, quote_ctx, option_code: str, stock_code: str, option_monitor=None) -> List[Dict[str, Any]]:
        """V2系统获取期权大单交易"""
        try:
            big_trades = []
            
            # 获取期权基本信息
            try:
                strike_price = self._parse_strike_from_code(option_code)
                option_type = self._parse_option_type_from_code(option_code)
                expiry_date = self._parse_expiry_from_code(option_code)
                option_info = {
                    'strike_price': strike_price,
                    'option_type': option_type,
                    'expiry_date': expiry_date
                }
                
                # 获取股票当前价格和名称
                current_stock_price = 0
                stock_name = ""
                
                if option_monitor and hasattr(option_monitor, 'stock_price_cache') and stock_code in option_monitor.stock_price_cache:
                    current_stock_price = option_monitor.stock_price_cache[stock_code]
                    if stock_code in self.stock_price_cache and isinstance(self.stock_price_cache[stock_code], dict):
                        stock_name = self.stock_price_cache[stock_code].get('name', '')
                    
                    price_diff = strike_price - current_stock_price if current_stock_price else 0
                    price_diff_pct = (price_diff / current_stock_price) * 100 if current_stock_price else 0
                    
                    option_info['stock_price'] = current_stock_price
                    option_info['stock_name'] = stock_name
                    option_info['price_diff'] = price_diff
                    option_info['price_diff_pct'] = price_diff_pct
                    
                    self.logger.info(f"V2期权详情 {option_code}: 执行价{strike_price:.2f} vs 股价{current_stock_price:.2f} ({stock_name})")
                else:
                    # 使用文件缓存或默认价格
                    file_info = self._load_stock_info_from_file(stock_code)
                    if file_info and file_info.get('price'):
                        current_stock_price = float(file_info['price'])
                        stock_name = file_info.get('name', '') or stock_code
                    else:
                        # 默认价格和名称
                        stock_names = {
                            'HK.00700': '腾讯控股', 'HK.09988': '阿里巴巴-SW', 'HK.03690': '美团-W',
                            'HK.01810': '小米集团-W', 'HK.09618': '京东集团-SW', 'HK.02318': '中国平安',
                            'HK.00388': '香港交易所', 'HK.00981': '中芯国际', 'HK.01024': '快手-W'
                        }
                        stock_name = stock_names.get(stock_code, stock_code)
                        
                        default_prices = {
                            'HK.00700': 600.0, 'HK.09988': 130.0, 'HK.03690': 120.0,
                            'HK.01810': 15.0, 'HK.09618': 120.0, 'HK.02318': 40.0,
                            'HK.00388': 300.0, 'HK.00981': 60.0, 'HK.01024': 50.0
                        }
                        current_stock_price = default_prices.get(stock_code, 100.0)
            except Exception as e:
                self.logger.error(f"V2解析{option_code}基本信息失败: {e}")
            
            # 获取市场快照
            try:
                ret, basic_info = quote_ctx.get_market_snapshot([option_code])
                if ret == ft.RET_OK and not basic_info.empty:
                    row = basic_info.iloc[0]
                    current_volume = row.get('volume', 0)
                    current_turnover = row.get('turnover', 0)
                    
                    # 优先使用API返回的执行价格
                    api_strike_price = row.get('strike_price', 0)
                    if api_strike_price and api_strike_price > 0:
                        strike_price = float(api_strike_price)
                        option_info['strike_price'] = strike_price
                        self.logger.debug(f"V2使用API执行价格: {option_code} = {strike_price}")
                    else:
                        # 如果API没有返回或为0，使用解析的价格
                        self.logger.debug(f"V2使用解析执行价格: {option_code} = {strike_price}")
                    
                    # 获取数据库中最后记录的交易量
                    last_recorded_volume = self._get_last_recorded_volume(option_code)
                    
                    # 检查当前数据是否符合大单条件
                    if (current_volume >= BIG_TRADE_CONFIG['min_volume_threshold'] and 
                        current_turnover >= BIG_TRADE_CONFIG['min_turnover_threshold'] and
                        current_volume != last_recorded_volume):
                        
                        volume_diff = current_volume - last_recorded_volume
                        
                        # 更新当日成交量缓存
                        self._update_today_volume_cache(option_code, current_volume)
                        
                        trade_info = {
                            'stock_code': stock_code,
                            'stock_name': option_info.get('stock_name', ''),
                            'option_code': option_code,
                            'timestamp': datetime.now().isoformat(),
                            'time_full': str(row.get('update_time') or row.get('time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                            'price': float(row.get('last_price', 0)),
                            'volume': int(current_volume),
                            'turnover': float(current_turnover),
                            'change_rate': float(row.get('change_rate', 0)),
                            'detected_time': datetime.now().isoformat(),
                            'data_type': 'v2_current',
                            'strike_price': option_info.get('strike_price', 0),
                            'option_type': option_info.get('option_type', '未知'),
                            'expiry_date': option_info.get('expiry_date', ''),
                            'stock_price': option_info.get('stock_price', 0),
                            'price_diff': option_info.get('price_diff', 0),
                            'price_diff_pct': option_info.get('price_diff_pct', 0),
                            'volume_diff': volume_diff,
                            'last_volume': last_recorded_volume
                        }
                        
                        # 获取买卖方向
                        direction = "Unknown"
                        direction_text = ""
                        try:
                            ret_ticker, ticker_data = quote_ctx.get_rt_ticker(option_code, 1)
                            if ret_ticker == ft.RET_OK and not ticker_data.empty:
                                ticker_row = ticker_data.iloc[0]
                                direction = ticker_row.get('ticker_direction', 'Unknown')
                                
                                if direction == "BUY":
                                    direction_text = "买入"
                                elif direction == "SELL":
                                    direction_text = "卖出"
                                elif direction == "NEUTRAL":
                                    direction_text = "中性"
                        except Exception as ticker_e:
                            self.logger.error(f"V2获取{option_code}逐笔成交方向失败: {ticker_e}")
                        
                        trade_info['direction'] = direction
                        big_trades.append(trade_info)
                        
                        direction_display = f", 方向: {direction_text}" if direction_text else ""
                        
                        self.logger.info(f"🔥 V2发现大单期权: {option_code}")
                        self.logger.info(f"   执行价格: {strike_price:.2f}, 类型: {option_type}{direction_display}")
                        self.logger.info(f"   成交量: {current_volume:,}张, 成交额: {current_turnover:,.0f}港币")
                
            except Exception as e:
                self.logger.error(f"V2获取{option_code}市场快照失败: {e}")
            
            return big_trades
            
        except Exception as e:
            self.logger.error(f"V2获取{option_code}大单交易失败: {e}")
            return []
    
    def save_big_options_summary(self, big_options: List[Dict[str, Any]]):
        """V2系统保存大单期权汇总到JSON文件"""
        try:
            summary = {
                'update_time': datetime.now().isoformat(),
                'total_count': len(big_options),
                'system_version': 'V2',
                'filter_conditions': BIG_TRADE_CONFIG,
                'big_options': big_options
            }
            
            if big_options:
                summary['statistics'] = self._calculate_statistics(big_options)
            
            def json_serializer(obj):
                """处理NumPy类型的JSON序列化器"""
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, pd.Series):
                    return obj.tolist()
                elif isinstance(obj, pd.DataFrame):
                    return obj.to_dict()
                else:
                    return str(obj)
            
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=json_serializer)
            
            self.logger.info(f"V2大单期权汇总已保存: {len(big_options)}笔交易")
            
        except Exception as e:
            self.logger.error(f"V2保存大单期权汇总失败: {e}")
            self.logger.error(traceback.format_exc())
    
    def _parse_strike_from_code(self, option_code: str) -> float:
        """从期权代码解析执行价格"""
        try:
            # 使用统一的期权代码解析器
            from .option_code_parser import parse_option_code
            
            option_info = parse_option_code(option_code)
            if option_info and option_info.get('strike_price') is not None:
                strike_price = float(option_info['strike_price'])
                self.logger.debug(f"V2使用解析器获取执行价格: {option_code} -> {strike_price}")
                return strike_price
            
            # 备用解析方法（已更新逻辑）
            if option_code.startswith('HK.'):
                # 格式: HK.TCH250929C680000
                import re
                pattern = r'HK\.([A-Z]{2,5})(\d{2})(\d{2})(\d{2})([CP])(\d+)'
                match = re.match(pattern, option_code)
                if match:
                    stock_symbol = match.group(1)  # 股票简称
                    price_str = match.group(6)     # 获取价格部分
                    price_int = int(price_str)
                    
                    # 根据股票简称和价格范围智能判断
                    # 高价股列表（通常股价在100港币以上）
                    high_price_stocks = ['TCH', 'HEX', 'MEI', 'JDC', 'ALI']  # 腾讯、港交所、美团、京东、阿里等
                    # 中价股列表（通常股价在20-100港币）
                    mid_price_stocks = ['BIU', 'KUA', 'ZMI']  # 小米、快手等
                    
                    if stock_symbol in high_price_stocks:
                        # 高价股：通常6位数除以1000，5位数除以100
                        if len(price_str) >= 6:
                            strike_price = float(price_int) / 1000.0
                        else:
                            strike_price = float(price_int) / 100.0
                    elif stock_symbol in mid_price_stocks:
                        # 中价股：6位数可能除以10000，5位数除以1000
                        if len(price_str) >= 6:
                            strike_price = float(price_int) / 10000.0
                        else:
                            strike_price = float(price_int) / 1000.0
                    else:
                        # 未知股票，根据数值大小智能判断
                        if len(price_str) >= 6:
                            if price_int >= 500000:  # 大于50万，可能是高价股
                                strike_price = float(price_int) / 1000.0
                            else:  # 小于50万，可能是低价股
                                strike_price = float(price_int) / 10000.0
                        elif len(price_str) >= 5:
                            if price_int >= 50000:  # 大于5万，除以1000
                                strike_price = float(price_int) / 1000.0
                            else:  # 小于5万，除以100
                                strike_price = float(price_int) / 100.0
                        else:
                            # 较短数字，除以100
                            strike_price = float(price_int) / 100.0
                    
                    self.logger.debug(f"V2备用解析执行价格: {option_code} -> {strike_price} (股票: {stock_symbol})")
                    return strike_price
                        
        except Exception as e:
            self.logger.error(f"V2解析执行价格失败: {e}")
        return 0.0
    
    def _parse_expiry_from_code(self, option_code: str) -> str:
        """从期权代码解析到期日"""
        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]
                matches = re.findall(r'(\d{6})(?=[CP])', code_part)
                if matches:
                    date_part = matches[-1]
                    year = int('20' + date_part[:2])
                    month = int(date_part[2:4])
                    day = int(date_part[4:6])
                    try:
                        dt = datetime(year, month, day)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        return ''
        except Exception as e:
            self.logger.error(f"V2解析到期日失败: {e}")
        return ''
    
    def _parse_option_type_from_code(self, option_code: str) -> str:
        """从期权代码解析类型"""
        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]
                m = re.search(r'\d+([CP])\d+', code_part)
                if m:
                    return 'Call' if m.group(1) == 'C' else 'Put'
                c_pos = code_part.rfind('C')
                p_pos = code_part.rfind('P')
                
                # 使用统一的期权代码解析器
                from .option_code_parser import get_option_type
                return get_option_type(option_code)
        except Exception as e:
            self.logger.error(f"V2解析期权类型失败: {e}")
        return '未知'

    def _calculate_statistics(self, big_options: List[Dict[str, Any]]) -> Dict[str, Any]:
        """V2系统计算统计信息"""
        if not big_options:
            return {}
        
        df = pd.DataFrame(big_options)
        
        stats = {
            'total_volume': int(df['volume'].sum()),
            'total_turnover': float(df['turnover'].sum()),
            'avg_volume': float(df['volume'].mean()),
            'avg_turnover': float(df['turnover'].mean()),
            'unique_stocks': int(df['stock_code'].nunique()),
            'unique_options': int(df['option_code'].nunique()),
        }
        
        # 按股票分组统计
        stock_stats = df.groupby('stock_code').agg({
            'volume': 'sum',
            'turnover': 'sum',
            'option_code': 'count'
        })
        
        stock_dict = {}
        for stock in stock_stats.index:
            stock_dict[str(stock)] = {
                'volume': int(stock_stats.loc[stock, 'volume']),
                'turnover': float(stock_stats.loc[stock, 'turnover']),
                'trade_count': int(stock_stats.loc[stock, 'option_code'])
            }
        
        stats['by_stock'] = stock_dict
        
        return stats
    
    def load_current_summary(self) -> Optional[Dict[str, Any]]:
        """V2系统加载当前的汇总数据"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"V2加载汇总数据失败: {e}")
            return None