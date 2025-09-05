# -*- coding: utf-8 -*-
"""
大单期权处理器
"""

import json
import logging
import pandas as pd
import time
import traceback
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from config import DATA_CONFIG, MONITOR_TIME, OPTION_FILTER
import futu as ft


class BigOptionsProcessor:
    """大单期权处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.BigOptionsProcessor')
        self.json_file = DATA_CONFIG['big_options_json']
        self.stock_price_cache = {}  # 缓存股价信息
        self.price_cache_time = {}   # 缓存时间
        self.last_option_volumes = {}  # 缓存上一次的期权交易量
    
    def get_recent_big_options(self, quote_ctx, stock_codes: List[str], option_monitor=None) -> List[Dict[str, Any]]:
        """获取最近2天的大单期权 - 可选使用option_monitor中的股价缓存"""
        all_big_options = []
        processed_stocks = set()  # 用于跟踪已处理的股票
        failed_stocks = set()     # 用于跟踪获取失败的股票
        
        self.logger.info(f"开始获取 {len(stock_codes)} 只股票的大单期权数据...")
        
        # 预先获取所有股票的价格，减少API调用，优先使用option_monitor中的股价缓存
        stock_prices = self._batch_get_stock_prices(quote_ctx, stock_codes, option_monitor)
        
        for i, stock_code in enumerate(stock_codes):
            try:
                # 跳过已处理或失败的股票
                if stock_code in processed_stocks:
                    self.logger.info(f"跳过已处理的股票: {stock_code}")
                    continue
                
                if stock_code in failed_stocks:
                    self.logger.info(f"跳过之前失败的股票: {stock_code}")
                    continue
                
                self.logger.info(f"正在处理 {i+1}/{len(stock_codes)}: {stock_code}")
                
                # 获取该股票的所有期权代码
                try:
                    option_codes = self._get_option_codes(quote_ctx, stock_code)
                except Exception as e:
                    self.logger.error(f"获取{stock_code}期权代码异常，跳过此股票: {e}")
                    failed_stocks.add(stock_code)
                    continue
                
                # 处理获取到的期权代码
                if option_codes:
                    self.logger.info(f"{stock_code} 获取到 {len(option_codes)} 个期权代码")
                    
                    # 处理所有期权
                    selected_options = option_codes
                    self.logger.info(f"将处理 {stock_code} 的 {len(selected_options)}/{len(option_codes)} 个期权")
                    
                    # 获取期权大单交易
                    stock_big_options = []
                    error_count = 0  # 记录连续错误次数
                    
                    for j, option_code in enumerate(selected_options):
                        try:
                            # 如果连续错误超过3次，跳过剩余期权
                            if error_count >= 3:
                                self.logger.warning(f"连续错误超过3次，跳过{stock_code}剩余期权")
                                break
                                
                            option_big_trades = self._get_option_big_trades(quote_ctx, option_code, stock_code)
                            if option_big_trades:
                                stock_big_options.extend(option_big_trades)
                                self.logger.info(f"期权 {j+1}/{len(selected_options)}: {option_code} 发现 {len(option_big_trades)} 笔大单")
                                error_count = 0  # 重置错误计数
                            
                            # 每处理5个期权暂停一下，避免API调用过于频繁
                            if (j + 1) % 5 == 0:
                                time.sleep(0.5)
                                
                        except Exception as e:
                            self.logger.error(f"处理期权 {option_code} 失败: {e}")
                            error_count += 1  # 增加错误计数
                    
                    # 添加到总结果
                    if stock_big_options:
                        self.logger.info(f"{stock_code} 发现 {len(stock_big_options)} 笔大单期权")
                        all_big_options.extend(stock_big_options)
                    else:
                        self.logger.info(f"{stock_code} 未发现大单期权")
                else:
                    self.logger.warning(f"{stock_code} 未获取到期权代码")
                
                # 标记为已处理
                processed_stocks.add(stock_code)
                
                # 每只股票处理完后暂停一下，避免API调用过于频繁
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"获取{stock_code}大单期权失败: {e}")
                self.logger.error(traceback.format_exc())
        
        # 按成交额降序排序，显示最大的交易在前
        all_big_options.sort(key=lambda x: x.get('turnover', 0), reverse=True)
        
        # 为每个期权添加正股价格和名称信息
        for option in all_big_options:
            stock_code = option.get('stock_code')
            if stock_code:
                # 使用预先获取的股票信息
                if stock_code in stock_prices:
                    stock_info = stock_prices[stock_code]
                    if isinstance(stock_info, dict):
                        option['stock_price'] = stock_info.get('price', 0)
                        option['stock_name'] = stock_info.get('name', '')
                    else:
                        # 兼容旧格式
                        option['stock_price'] = stock_info
                else:
                    # 如果没有预先获取到，尝试单独获取
                    stock_info = self.get_stock_price(quote_ctx, stock_code)
                    if isinstance(stock_info, dict):
                        option['stock_price'] = stock_info.get('price', 0)
                        option['stock_name'] = stock_info.get('name', '')
                    else:
                        option['stock_price'] = stock_info
        
        self.logger.info(f"总共发现 {len(all_big_options)} 笔大单期权")
        
        # 打印每只股票的大单数量
        stock_counts = {}
        for option in all_big_options:
            stock_code = option.get('stock_code', 'Unknown')
            if stock_code not in stock_counts:
                stock_counts[stock_code] = 0
            stock_counts[stock_code] += 1
        
        for stock_code, count in stock_counts.items():
            self.logger.info(f"📊 {stock_code}: {count} 笔大单")
        
        return all_big_options
    
    def _batch_get_stock_prices(self, quote_ctx, stock_codes: List[str], option_monitor=None) -> Dict[str, Dict[str, Any]]:
        """批量获取股票价格和名称 - 优先使用option_monitor中的股价缓存"""
        result = {}
        current_time = datetime.now()
        
        # 如果提供了option_monitor实例，优先使用其股价缓存
        if option_monitor and hasattr(option_monitor, 'stock_price_cache'):
            self.logger.info(f"使用option_monitor中的股价缓存")
            
            for stock_code in stock_codes:
                # 从option_monitor获取股价
                if stock_code in option_monitor.stock_price_cache:
                    price = option_monitor.stock_price_cache[stock_code]
                    
                    # 构建股票信息字典
                    stock_info = {
                        'price': price,
                        'name': ''  # option_monitor中可能没有存储名称
                    }
                    
                    # 如果本地缓存中有名称信息，补充名称
                    if stock_code in self.stock_price_cache and isinstance(self.stock_price_cache[stock_code], dict):
                        old_info = self.stock_price_cache[stock_code]
                        if 'name' in old_info and old_info['name']:
                            stock_info['name'] = old_info['name']
                    
                    # 更新结果和本地缓存
                    result[stock_code] = stock_info
                    self.stock_price_cache[stock_code] = stock_info
                    self.price_cache_time[stock_code] = current_time
                    self.logger.debug(f"从option_monitor获取股价: {stock_code} = {price}")
                else:
                    # 如果option_monitor中没有，检查本地缓存
                    if stock_code in self.stock_price_cache and stock_code in self.price_cache_time:
                        if (current_time - self.price_cache_time[stock_code]).seconds < 300:  # 5分钟 = 300秒
                            result[stock_code] = self.stock_price_cache[stock_code]
                            continue
        else:
            # 检查哪些股票需要更新价格
            for stock_code in stock_codes:
                # 如果缓存中有且未过期，使用缓存
                if stock_code in self.stock_price_cache and stock_code in self.price_cache_time:
                    if (current_time - self.price_cache_time[stock_code]).seconds < 300:  # 5分钟 = 300秒
                        result[stock_code] = self.stock_price_cache[stock_code]
                        continue
        
        # 找出仍需要更新的股票
        stocks_to_update = [code for code in stock_codes if code not in result]
        
        if not stocks_to_update:
            self.logger.info("所有股价都已获取，无需更新")
            return result
        
        # 批量获取股价和名称
        try:
            self.logger.info(f"批量获取 {len(stocks_to_update)} 只股票的价格和名称...")
            ret, data = quote_ctx.get_market_snapshot(stocks_to_update)
            
            if ret == ft.RET_OK and not data.empty:
                for _, row in data.iterrows():
                    code = row['code']
                    price = float(row['last_price'])
                    name = row.get('name', '') or row.get('stock_name', '')  # 获取股票名称
                    
                    # 存储价格和名称
                    stock_info = {
                        'price': price,
                        'name': name
                    }
                    
                    result[code] = stock_info
                    self.stock_price_cache[code] = stock_info
                    self.price_cache_time[code] = current_time
                    self.logger.debug(f"获取股票信息: {code} = {price} ({name})")
                
                self.logger.info(f"成功获取 {len(data)} 只股票的价格和名称")
            else:
                self.logger.warning(f"批量获取股票信息失败: {ret}")
                # 使用缓存中的旧数据
                for stock_code in stocks_to_update:
                    if stock_code in self.stock_price_cache:
                        result[stock_code] = self.stock_price_cache[stock_code]
                        price_info = self.stock_price_cache[stock_code]
                        if isinstance(price_info, dict):
                            price = price_info.get('price', 0)
                            name = price_info.get('name', '')
                            self.logger.debug(f"使用旧缓存的股票信息: {stock_code} = {price} ({name})")
                        else:
                            # 兼容旧格式的缓存
                            self.logger.debug(f"使用旧缓存的股价: {stock_code} = {price_info}")
        
        except Exception as e:
            self.logger.error(f"批量获取股票信息异常: {e}")
            self.logger.error(traceback.format_exc())
            # 使用缓存中的旧数据
            for stock_code in stocks_to_update:
                if stock_code in self.stock_price_cache:
                    result[stock_code] = self.stock_price_cache[stock_code]
        
        return result
    
    def get_stock_price(self, quote_ctx, stock_code: str, option_monitor=None) -> Dict[str, Any]:
        """获取股票当前价格和名称（带缓存）- 优先使用option_monitor中的股价缓存"""
        try:
            current_time = datetime.now()
            
            # 如果提供了option_monitor实例，优先使用其股价缓存
            if option_monitor and hasattr(option_monitor, 'stock_price_cache') and stock_code in option_monitor.stock_price_cache:
                price = option_monitor.stock_price_cache[stock_code]
                
                # 构建股票信息字典
                stock_info = {
                    'price': price,
                    'name': ''  # option_monitor中可能没有存储名称
                }
                
                # 如果本地缓存中有名称信息，补充名称
                if stock_code in self.stock_price_cache and isinstance(self.stock_price_cache[stock_code], dict):
                    old_info = self.stock_price_cache[stock_code]
                    if 'name' in old_info and old_info['name']:
                        stock_info['name'] = old_info['name']
                
                # 更新本地缓存
                self.stock_price_cache[stock_code] = stock_info
                self.price_cache_time[stock_code] = current_time
                self.logger.debug(f"从option_monitor获取股价: {stock_code} = {price}")
                
                return stock_info
            
            # 检查本地缓存
            if (stock_code in self.stock_price_cache and 
                stock_code in self.price_cache_time and
                (current_time - self.price_cache_time[stock_code]).seconds < 300):  # 缓存5分钟
                
                stock_info = self.stock_price_cache[stock_code]
                if isinstance(stock_info, dict):
                    price = stock_info.get('price', 0)
                    name = stock_info.get('name', '')
                    self.logger.debug(f"使用缓存的股票信息: {stock_code} = {price} ({name})")
                else:
                    # 兼容旧格式
                    self.logger.debug(f"使用缓存的股价: {stock_code} = {stock_info}")
                    # 转换为新格式
                    stock_info = {'price': stock_info, 'name': ''}
                    self.stock_price_cache[stock_code] = stock_info
                
                return stock_info
            
            # 获取实时股票信息
            ret, snap_data = quote_ctx.get_market_snapshot([stock_code])
            if ret == ft.RET_OK and not snap_data.empty:
                row = snap_data.iloc[0]
                price = float(row['last_price'])
                name = row.get('name', '') or row.get('stock_name', '')  # 获取股票名称
                
                # 更新缓存
                stock_info = {'price': price, 'name': name}
                self.stock_price_cache[stock_code] = stock_info
                self.price_cache_time[stock_code] = current_time
                self.logger.debug(f"获取股票信息: {stock_code} = {price} ({name})")
                
                # 如果提供了option_monitor实例，同时更新其缓存
                if option_monitor and hasattr(option_monitor, 'stock_price_cache'):
                    option_monitor.stock_price_cache[stock_code] = price
                    if hasattr(option_monitor, 'price_update_time'):
                        option_monitor.price_update_time[stock_code] = current_time
                
                return stock_info
            else:
                self.logger.warning(f"获取{stock_code}股票信息失败")
                
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
                    self.logger.info(f"使用默认股票信息: {stock_code} = {stock_info['price']} ({stock_info['name']})")
                    self.stock_price_cache[stock_code] = stock_info
                    self.price_cache_time[stock_code] = current_time
                    return stock_info
                
                return {'price': 0.0, 'name': ''}
        except Exception as e:
            self.logger.error(f"获取{stock_code}股票信息异常: {e}")
            
            # 如果缓存中有旧数据，返回旧数据
            if stock_code in self.stock_price_cache:
                stock_info = self.stock_price_cache[stock_code]
                if isinstance(stock_info, dict):
                    price = stock_info.get('price', 0)
                    name = stock_info.get('name', '')
                    self.logger.debug(f"异常时使用旧缓存的股票信息: {stock_code} = {price} ({name})")
                else:
                    # 兼容旧格式
                    self.logger.debug(f"异常时使用旧缓存的股价: {stock_code} = {stock_info}")
                    # 转换为新格式
                    stock_info = {'price': stock_info, 'name': ''}
                return stock_info
            
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
                self.logger.info(f"异常时使用默认股票信息: {stock_code} = {stock_info['price']} ({stock_info['name']})")
                self.stock_price_cache[stock_code] = stock_info
                self.price_cache_time[stock_code] = current_time
                return stock_info
                
            return {'price': 0.0, 'name': ''}
    
    def _get_stock_big_options(self, quote_ctx, stock_code: str) -> List[Dict[str, Any]]:
        """获取单个股票的大单期权"""
        big_options = []
        
        try:
            # 获取期权链
            option_codes = self._get_option_codes(quote_ctx, stock_code)
            self.logger.info(f"获取{stock_code}期权: {len(option_codes)}个")
            for option_code in option_codes:
                option_big_trades = self._get_option_big_trades(quote_ctx, option_code, stock_code)
                big_options.extend(option_big_trades)
                
        except Exception as e:
            self.logger.error(f"获取{stock_code}期权大单异常: {e}")
        
        return big_options
    
    def _get_option_codes(self, quote_ctx, stock_code: str) -> List[str]:
        """获取期权代码列表"""
        try:
            import futu as ft
            
            option_codes = []
            
            # 首先获取当前股价
            try:
                ret_snap, snap_data = quote_ctx.get_market_snapshot([stock_code])
                if ret_snap != ft.RET_OK or snap_data.empty:
                    self.logger.warning(f"获取{stock_code}市场快照失败，尝试使用默认价格")
                    # 使用默认价格作为回退
                    if stock_code == 'HK.00700':  # 腾讯
                        current_price = 600.0
                    elif stock_code == 'HK.09988':  # 阿里巴巴
                        current_price = 80.0
                    elif stock_code == 'HK.03690':  # 美团
                        current_price = 120.0
                    elif stock_code == 'HK.01810':  # 小米
                        current_price = 15.0
                    elif stock_code == 'HK.09618':  # 京东
                        current_price = 120.0
                    elif stock_code == 'HK.02318':  # 中国平安
                        current_price = 40.0
                    elif stock_code == 'HK.00388':  # 港交所
                        current_price = 300.0
                    else:
                        current_price = 100.0  # 默认价格
                else:
                    current_price = snap_data.iloc[0]['last_price']
                
                self.logger.info(f"{stock_code}当前股价: {current_price}")
                
                # 基于股价设定期权执行价格过滤范围
                price_range = OPTION_FILTER.get('price_range', 0.2)  # 配置中是20%
                price_lower = current_price * (1 - price_range)
                price_upper = current_price * (1 + price_range)
                self.logger.info(f"筛选价格范围: {price_lower:.2f} - {price_upper:.2f} (±{price_range*100}%)")
            except Exception as e:
                self.logger.error(f"获取{stock_code}当前股价失败: {e}")
                # 使用默认价格作为回退
                current_price = 100.0
                price_range = 0.5  # 使用更大的范围
                price_lower = current_price * (1 - price_range)
                price_upper = current_price * (1 + price_range)
                self.logger.info(f"使用默认价格: {current_price}，筛选范围: {price_lower:.2f} - {price_upper:.2f} (±{price_range*100}%)")
            
            # 获取期权到期日
            try:
                ret, expiry_data = quote_ctx.get_option_expiration_date(stock_code)
                if ret != ft.RET_OK:
                    self.logger.warning(f"{stock_code}没有期权合约或API调用失败: {ret}")
                    return []
                
                if expiry_data.empty:
                    self.logger.warning(f"{stock_code}暂无期权合约")
                    return []
                
                # 只获取最近1个月内的期权链
                now = datetime.now()
                one_month_later = now + timedelta(days=30)
                
                # 筛选1个月内的到期日
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
                
                recent_dates = pd.DataFrame(valid_dates) if valid_dates else expiry_data.head(2)  # 如果没有1个月内的，就取最近的2个
                self.logger.info(f"{stock_code} 找到 {len(expiry_data)} 个到期日，筛选出 {len(recent_dates)} 个1个月内的到期日")
                
                # 记录API调用失败的到期日，以便重试
                failed_dates = []
                
                for _, row in recent_dates.iterrows():
                    try:
                        # 使用正确的列名 strike_time
                        expiry_date = row['strike_time']
                        
                        # 尝试正确的API调用方式
                        option_data = None
                        ret2 = None
                        
                        # 确保日期格式正确
                        date_str = expiry_date
                        if isinstance(expiry_date, pd.Timestamp):
                            date_str = expiry_date.strftime('%Y-%m-%d')
                        elif isinstance(expiry_date, datetime):
                            date_str = expiry_date.strftime('%Y-%m-%d')
                        
                        # 直接使用完整参数获取期权链（方式3）
                        self.logger.debug(f"获取 {stock_code} {date_str} 的期权链")
                        ret2, option_data = quote_ctx.get_option_chain(
                            code=stock_code, 
                            start=date_str, 
                            end=date_str,
                            option_type=ft.OptionType.ALL,
                            option_cond_type=ft.OptionCondType.ALL
                        )
                                
                        if ret2 == ft.RET_OK and not option_data.empty:
                            self.logger.info(f"API调用成功: {stock_code} {expiry_date}, 获取到 {len(option_data)} 个期权")
                        else:
                            self.logger.warning(f"API调用返回空数据: {stock_code} {expiry_date}, ret={ret2}")
                            failed_dates.append(expiry_date)
                        
                        # 添加短暂延迟，避免API限流
                        time.sleep(0.5)
                        
                        if ret2 == ft.RET_OK and not option_data.empty:
                            # 打印所有期权的执行价格用于调试
                            self.logger.info(f"{stock_code} {expiry_date}到期的期权执行价格范围: {option_data['strike_price'].min():.2f} - {option_data['strike_price'].max():.2f}")
                            self.logger.info(f"{stock_code}当前股价: {current_price:.2f}, 筛选范围: {price_lower:.2f} - {price_upper:.2f}")
                            
                            # 筛选执行价格在当前股价上下范围内的期权
                            filtered_options = option_data[
                                (option_data['strike_price'] >= price_lower) & 
                                (option_data['strike_price'] <= price_upper)
                            ]
                            
                            if not filtered_options.empty:
                                # 打印筛选后的期权执行价格
                                strike_prices = filtered_options['strike_price'].tolist()
                                self.logger.info(f"{stock_code} {expiry_date}到期的期权中有{len(filtered_options)}个在价格范围内")
                                self.logger.info(f"筛选后的执行价格: {[f'{price:.2f}' for price in strike_prices[:10]]}{'...' if len(strike_prices) > 10 else ''}")
                                option_codes.extend(filtered_options['code'].tolist())
                            else:
                                self.logger.info(f"{stock_code} {expiry_date}到期的期权没有在价格范围内的")
                                # 如果没有在范围内的期权，尝试放宽范围
                                wider_range = price_range * 1.5  # 增加50%的范围
                                wider_lower = current_price * (1 - wider_range)
                                wider_upper = current_price * (1 + wider_range)
                                
                                # 使用更宽的范围再次筛选
                                wider_filtered = option_data[
                                    (option_data['strike_price'] >= wider_lower) & 
                                    (option_data['strike_price'] <= wider_upper)
                                ]
                                
                                if not wider_filtered.empty:
                                    self.logger.info(f"使用更宽的范围 (±{wider_range*100}%) 找到 {len(wider_filtered)} 个期权")
                                    # 只取最接近当前价格的几个期权
                                    # 使用.loc避免SettingWithCopyWarning
                                    wider_filtered = wider_filtered.copy()  # 创建明确的副本
                                    wider_filtered.loc[:, 'price_diff'] = abs(wider_filtered['strike_price'] - current_price)
                                    closest_options = wider_filtered.nsmallest(5, 'price_diff')
                                    option_codes.extend(closest_options['code'].tolist())
                                    self.logger.info(f"添加 {len(closest_options)} 个最接近当前价格的期权")
                                else:
                                    # 显示最接近的期权执行价格
                                    closest_strikes = option_data['strike_price'].nsmallest(3).tolist() + option_data['strike_price'].nlargest(3).tolist()
                                    self.logger.info(f"最接近的执行价格: {[f'{price:.2f}' for price in sorted(set(closest_strikes))]}")
                        else:
                            self.logger.warning(f"无法获取 {stock_code} {expiry_date} 的期权链")
                    except Exception as e:
                        self.logger.warning(f"获取{stock_code}期权链失败: {e}")
                        failed_dates.append(expiry_date)
                        continue
                
                # 如果有失败的日期，尝试使用另一种方式获取
                if failed_dates and not option_codes:
                    self.logger.info(f"{stock_code} 有 {len(failed_dates)} 个到期日获取失败，尝试使用替代方法")
                    try:
                        # 添加延迟，避免API调用过于频繁
                        time.sleep(1)
                        
                        # 尝试获取所有期权，不按到期日筛选
                        self.logger.info(f"尝试获取 {stock_code} 的所有期权...")
                        ret_all, all_options = quote_ctx.get_option_chain(stock_code)
                        
                        if ret_all == ft.RET_OK and not all_options.empty:
                            self.logger.info(f"成功获取 {stock_code} 的所有期权: {len(all_options)} 个")
                        else:
                            self.logger.warning(f"获取 {stock_code} 的所有期权失败: ret={ret_all}")
                            # 如果获取失败，直接返回已有的期权代码（可能为空）
                            return option_codes
                            
                            # 筛选执行价格在范围内的期权
                            filtered_all = all_options[
                                (all_options['strike_price'] >= price_lower) & 
                                (all_options['strike_price'] <= price_upper)
                            ]
                            
                            if not filtered_all.empty:
                                self.logger.info(f"筛选出 {len(filtered_all)} 个在价格范围内的期权")
                                option_codes.extend(filtered_all['code'].tolist())
                            else:
                                self.logger.info(f"没有在价格范围内的期权，尝试获取最接近的期权")
                                # 计算与当前价格的差距
                                all_options['price_diff'] = abs(all_options['strike_price'] - current_price)
                                # 获取最接近的10个期权
                                closest_options = all_options.nsmallest(10, 'price_diff')
                                option_codes.extend(closest_options['code'].tolist())
                                self.logger.info(f"添加 {len(closest_options)} 个最接近当前价格的期权")
                    except Exception as all_err:
                        self.logger.error(f"尝试获取所有期权失败: {all_err}")
                
            except Exception as e:
                self.logger.debug(f"获取{stock_code}期权到期日失败: {e}")
                return []
            
            if option_codes:
                self.logger.info(f"{stock_code}获取到{len(option_codes)}个期权合约")
            else:
                self.logger.debug(f"{stock_code}未找到期权合约")
            
            return option_codes
            
        except Exception as e:
            self.logger.error(f"获取{stock_code}期权代码失败: {e}")
            return []
    
    def _get_option_big_trades(self, quote_ctx, option_code: str, stock_code: str, option_monitor=None) -> List[Dict[str, Any]]:
        """获取期权大单交易 - 可选使用option_monitor中的股价缓存"""
        try:
            import futu as ft
            
            big_trades = []
            
            # 获取期权基本信息，包括执行价格和期权类型
            # 构造期权基本信息（兼容无 get_option_info）
            try:
                strike_price = self._parse_strike_from_code(option_code)
                option_type = self._parse_option_type_from_code(option_code)
                expiry_date = self._parse_expiry_from_code(option_code)
                option_info = {
                    'strike_price': strike_price,
                    'option_type': option_type,
                    'expiry_date': expiry_date
                }
                # 获取股票当前价格和名称用于对比和显示
                current_stock_price = 0
                stock_name = ""
                
                # 优先使用option_monitor中的股价缓存
                if option_monitor and hasattr(option_monitor, 'stock_price_cache') and stock_code in option_monitor.stock_price_cache:
                    current_stock_price = option_monitor.stock_price_cache[stock_code]
                    # 尝试从本地缓存获取股票名称
                    if stock_code in self.stock_price_cache and isinstance(self.stock_price_cache[stock_code], dict):
                        stock_name = self.stock_price_cache[stock_code].get('name', '')
                    
                    self.logger.debug(f"使用option_monitor中的股价: {stock_code} = {current_stock_price}")
                    
                    # 计算价格差异
                    price_diff = strike_price - current_stock_price if current_stock_price else 0
                    price_diff_pct = (price_diff / current_stock_price) * 100 if current_stock_price else 0
                    
                    # 更新期权信息
                    option_info['stock_price'] = current_stock_price
                    option_info['stock_name'] = stock_name
                    option_info['price_diff'] = price_diff
                    option_info['price_diff_pct'] = price_diff_pct
                    
                    self.logger.info(f"期权详情 {option_code}: 执行价{strike_price:.2f} vs 股价{current_stock_price:.2f} ({stock_name}), 差价{price_diff:+.2f}({price_diff_pct:+.1f}%), 类型:{option_type}")
                else:
                    # 如果没有option_monitor或其中没有股价缓存，则使用API获取
                    try:
                        ret_stock, stock_snap = quote_ctx.get_market_snapshot([stock_code])
                        if ret_stock == ft.RET_OK and not stock_snap.empty:
                            row = stock_snap.iloc[0]
                            current_stock_price = row['last_price']
                            stock_name = row.get('name', '') or row.get('stock_name', '')  # 获取股票名称
                            price_diff = strike_price - current_stock_price if current_stock_price else 0
                            price_diff_pct = (price_diff / current_stock_price) * 100 if current_stock_price else 0
                            option_info['stock_price'] = current_stock_price
                            option_info['stock_name'] = stock_name
                            option_info['price_diff'] = price_diff
                            option_info['price_diff_pct'] = price_diff_pct
                            
                            # 如果有option_monitor，更新其股价缓存
                            if option_monitor and hasattr(option_monitor, 'stock_price_cache'):
                                option_monitor.stock_price_cache[stock_code] = current_stock_price
                                if hasattr(option_monitor, 'price_update_time'):
                                    option_monitor.price_update_time[stock_code] = datetime.now()
                            
                            self.logger.info(f"期权详情 {option_code}: 执行价{strike_price:.2f} vs 股价{current_stock_price:.2f} ({stock_name}), 差价{price_diff:+.2f}({price_diff_pct:+.1f}%), 类型:{option_type}")
                    except Exception as stock_e:
                        self.logger.debug(f"获取{stock_code}股价用于对比失败: {stock_e}")
            except Exception as e:
                self.logger.debug(f"解析{option_code}基本信息失败: {e}")
            
            # 尝试获取市场快照
            try:
                ret, basic_info = quote_ctx.get_market_snapshot([option_code])
                if ret == ft.RET_OK and not basic_info.empty:
                    # 获取当前成交量和成交额
                    row = basic_info.iloc[0]
                    current_volume = row.get('volume', 0)
                    current_turnover = row.get('turnover', 0)
                    
                    # 获取上一次的交易量
                    last_volume = self.last_option_volumes.get(option_code, 0)
                    
                    # 检查当前数据是否符合大单条件，并且交易量有变化
                    if (current_volume >= OPTION_FILTER['min_volume'] and 
                        current_turnover >= OPTION_FILTER['min_turnover'] and
                        current_volume != last_volume):
                        
                        # 计算变化量
                        volume_diff = current_volume - last_volume
                        
                        # 更新缓存的交易量
                        self.last_option_volumes[option_code] = current_volume
                        
                        trade_info = {
                            'stock_code': stock_code,
                            'stock_name': option_info.get('stock_name', ''),  # 添加股票名称
                            'option_code': option_code,
                            'timestamp': datetime.now().isoformat(),
                            'time_full': str(row.get('update_time') or row.get('time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                            'price': float(row.get('last_price', 0)),
                            'volume': int(current_volume),
                            'turnover': float(current_turnover),
                            'change_rate': float(row.get('change_rate', 0)),
                            'detected_time': datetime.now().isoformat(),
                            'data_type': 'current',
                            # 添加期权详细信息
                            'strike_price': option_info.get('strike_price', 0),
                            'option_type': option_info.get('option_type', '未知'),
                            'expiry_date': option_info.get('expiry_date', ''),
                            # 添加正股信息
                            'stock_price': option_info.get('stock_price', 0),
                            'price_diff': option_info.get('price_diff', 0),
                            'price_diff_pct': option_info.get('price_diff_pct', 0),
                            # 添加变化量
                            'volume_diff': volume_diff,
                            'last_volume': last_volume
                        }
                        
                        # 获取买卖方向 - 使用get_ticker接口
                        direction = "Unknown"
                        direction_text = ""
                        try:
                            # 获取最近的逐笔成交记录
                            ret_ticker, ticker_data = quote_ctx.get_rt_ticker(option_code, 1)  # 只获取最新的一条记录
                            if ret_ticker == ft.RET_OK and not ticker_data.empty:
                                # 获取最新一条记录的方向
                                ticker_row = ticker_data.iloc[0]
                                direction = ticker_row.get('ticker_direction', 'Unknown')
                                
                                if direction == "BUY":
                                    direction_text = "买入"
                                elif direction == "SELL":
                                    direction_text = "卖出"
                                elif direction == "NEUTRAL":
                                    direction_text = "中性"
                                self.logger.debug(f"从get_rt_ticker获取到买卖方向: {direction} ({direction_text})")
                        except Exception as ticker_e:
                            self.logger.debug(f"获取{option_code}逐笔成交方向失败: {ticker_e}")
                        
                        # 添加方向到交易信息
                        trade_info['direction'] = direction
                        
                        big_trades.append(trade_info)
                        strike_price = option_info.get('strike_price', 0)
                        option_type = option_info.get('option_type', '未知')
                        trade_info['direction'] = direction
                        
                        direction_display = f", 方向: {direction_text}" if direction_text else ""
                        
                        self.logger.info(f"🔥 发现大单期权: {option_code}")
                        self.logger.info(f"   执行价格: {strike_price:.2f}, 类型: {option_type}{direction_display}")
                        self.logger.info(f"   成交量: {current_volume:,}手, 成交额: {current_turnover:,.0f}港币")
                        self.logger.info(f"   当前价格: {row.get('last_price', 0):.4f}, 涨跌幅: {row.get('change_rate', 0):+.2f}%")
                
            except Exception as e:
                self.logger.debug(f"获取{option_code}市场快照失败: {e}")
            
            # 如果当前没有大单，使用报价接口作为回退
            if not big_trades:
                try:
                    ret_q, q_df = quote_ctx.get_stock_quote([option_code])
                    if ret_q == ft.RET_OK and not q_df.empty:
                        row2 = q_df.iloc[0]
                        volume2 = int(row2.get('volume', 0))
                        turnover2 = float(row2.get('turnover', 0))
                        # 获取上一次的交易量
                        last_volume = self.last_option_volumes.get(option_code, 0)
                        
                        if (volume2 >= OPTION_FILTER['min_volume'] and 
                            turnover2 >= OPTION_FILTER['min_turnover'] and
                            volume2 != last_volume):
                            
                            # 计算变化量
                            volume_diff = volume2 - last_volume
                            
                            # 更新缓存的交易量
                            self.last_option_volumes[option_code] = volume2
                            time_str = row2.get('update_time') or row2.get('time') or ''
                            time_full = time_str if time_str else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            # 获取买卖方向 - 使用get_ticker接口
                            direction = "Unknown"
                            try:
                                # 获取最近的逐笔成交记录
                                ret_ticker, ticker_data = quote_ctx.get_rt_ticker(option_code, 1)  # 只获取最新的一条记录
                                if ret_ticker == ft.RET_OK and not ticker_data.empty:
                                    # 获取最新一条记录的方向
                                    ticker_row = ticker_data.iloc[0]
                                    direction = ticker_row.get('ticker_direction', 'Unknown')
                                    self.logger.debug(f"报价回退模式：从get_rt_ticker获取到买卖方向: {direction}")
                            except Exception as ticker_e:
                                self.logger.debug(f"报价回退模式：获取{option_code}逐笔成交方向失败: {ticker_e}")
                            
                            quote_trade = {
                                'stock_code': stock_code,
                                'stock_name': option_info.get('stock_name', ''),  # 添加股票名称
                                'option_code': option_code,
                                'timestamp': time_full,
                                'time_full': time_full,
                                'price': float(row2.get('last_price', 0)),
                                'volume': volume2,
                                'turnover': turnover2,
                                'change_rate': float(row2.get('change_rate', 0)),
                                'detected_time': datetime.now().isoformat(),
                                'data_type': 'quote',
                                # 添加期权详细信息
                                'strike_price': option_info.get('strike_price', 0),
                                'option_type': option_info.get('option_type', '未知'),
                                'expiry_date': option_info.get('expiry_date', ''),
                                # 添加正股信息
                                'stock_price': option_info.get('stock_price', 0),
                                'price_diff': option_info.get('price_diff', 0),
                                'price_diff_pct': option_info.get('price_diff_pct', 0),
                                # 添加买卖方向
                                'direction': direction,
                                # 添加变化量
                                'volume_diff': volume_diff,
                                'last_volume': last_volume
                            }
                            big_trades.append(quote_trade)
                            
                            # 显示买卖方向
                            direction_text = ""
                            if direction == "BUY":
                                direction_text = "买入"
                            elif direction == "SELL":
                                direction_text = "卖出"
                            elif direction == "NEUTRAL":
                                direction_text = "中性"
                            
                            direction_display = f", 方向: {direction_text}" if direction_text else ""
                            
                            self.logger.info(f"📊 报价回退发现大单: {option_code}")
                            self.logger.info(f"   执行价格: {option_info.get('strike_price', 0):.2f}, 类型: {option_info.get('option_type', '未知')}{direction_display}")
                            self.logger.info(f"   成交量: {volume2:,}手, 成交额: {turnover2:,.0f}港币")
                except Exception as e:
                    self.logger.debug(f"报价回退失败: {e}")
            
            return big_trades
            
        except Exception as e:
            self.logger.debug(f"获取{option_code}大单交易失败: {e}")
            return []
    
    def save_big_options_summary(self, big_options: List[Dict[str, Any]]):
        """保存大单期权汇总到JSON文件"""
        try:
            # 准备汇总数据
            summary = {
                'update_time': datetime.now().isoformat(),
                'total_count': len(big_options),
                'lookback_days': MONITOR_TIME['lookback_days'],
                'filter_conditions': OPTION_FILTER,
                'big_options': big_options
            }
            
            # 添加统计信息
            if big_options:
                summary['statistics'] = self._calculate_statistics(big_options)
            
            # 定义JSON序列化器，处理NumPy类型
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
            
            # 保存到JSON文件
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=json_serializer)
            
            self.logger.info(f"大单期权汇总已保存: {len(big_options)}笔交易")
            
        except Exception as e:
            self.logger.error(f"保存大单期权汇总失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _parse_strike_from_code(self, option_code: str) -> float:
        """从期权代码解析执行价格（使用末尾的 C/P 标识）"""
        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]  # 去掉 HK.
                # 优先用正则匹配末尾的 C/P + 数字
                m = re.search(r'([CP])(\d+)$', code_part)
                if m:
                    digits = m.group(2)
                    return float(digits) / 1000.0
                # 回退：取最后一个 C 或 P 之后的所有数字
                opt_pos = max(code_part.rfind('C'), code_part.rfind('P'))
                if opt_pos != -1:
                    tail = code_part[opt_pos + 1:]
                    digits = ''.join(ch for ch in tail if ch.isdigit())
                    if digits:
                        return float(digits) / 1000.0
        except Exception as e:
            self.logger.debug(f"解析执行价格失败: {e}")
        return 0.0
    
    def _parse_expiry_from_code(self, option_code: str) -> str:
        """从期权代码解析到期日（使用紧邻最后 C/P 之前的6位数字 YYMMDD）"""
        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]  # 去掉 HK.
                # 找到所有“6位数字 + 紧随其后的 C/P”，取最后一次匹配
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
            self.logger.debug(f"解析到期日失败: {e}")
        return ''
    
    def _parse_option_type_from_code(self, option_code: str) -> str:
        """从期权代码解析类型（基于末尾的 C/P 标识）"""
        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]  # 去掉 HK.
                # 优先：匹配末尾的 C/P+数字
                m = re.search(r'([CP])(\d+)$', code_part)
                if m:
                    return 'Call' if m.group(1) == 'C' else 'Put'
                # 回退：比较最后一次出现的 C 与 P
                c_pos = code_part.rfind('C')
                p_pos = code_part.rfind('P')
                if c_pos == -1 and p_pos == -1:
                    return '未知'
                return 'Call' if c_pos > p_pos else 'Put'
        except Exception as e:
            self.logger.debug(f"解析期权类型失败: {e}")
        return '未知'

    def _calculate_statistics(self, big_options: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        if not big_options:
            return {}
        
        # 转换为DataFrame便于统计
        df = pd.DataFrame(big_options)
        
        # 确保使用Python原生类型，而不是NumPy类型
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
        
        # 转换为字典格式，确保使用Python原生类型
        stock_dict = {}
        for stock in stock_stats.index:
            stock_dict[str(stock)] = {  # 确保键是字符串
                'volume': int(stock_stats.loc[stock, 'volume']),
                'turnover': float(stock_stats.loc[stock, 'turnover']),
                'trade_count': int(stock_stats.loc[stock, 'option_code'])
            }
        
        stats['by_stock'] = stock_dict
        
        return stats
    
    def load_current_summary(self) -> Optional[Dict[str, Any]]:
        """加载当前的汇总数据"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"加载汇总数据失败: {e}")
            return None
    
    def process_big_options_summary(self, start_date: datetime, end_date: datetime) -> Optional[Dict[str, Any]]:
        """处理大单期权汇总（用于强制刷新）"""
        try:
            # 这里需要连接到Futu OpenD来获取实时数据
            # 为了简化，我们先返回当前已有的数据
            current_summary = self.load_current_summary()
            
            if current_summary:
                # 更新时间戳
                current_summary['update_time'] = datetime.now().isoformat()
                # 保存更新后的数据
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump(current_summary, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"强制刷新汇总数据完成: {current_summary.get('total_count', 0)}笔交易")
                return current_summary
            else:
                self.logger.warning("没有找到现有汇总数据")
                return None
                
        except Exception as e:
            self.logger.error(f"处理大单期权汇总失败: {e}")
            return None