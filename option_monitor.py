# -*- coding: utf-8 -*-
"""
港股期权大单监控主程序
"""

import time
import logging
import traceback
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import signal
import sys
import re
import os

# 第三方库
try:
    import futu as ft
    import json
except ImportError as e:
    print(f"请安装必要的依赖包: {e}")
    print("pip install futu-api akshare tushare")
    sys.exit(1)

from config import *
from utils.logger import setup_logger
from utils.notifier import Notifier
from utils.data_handler import DataHandler
from utils.mac_notifier import MacNotifier
from utils.big_options_processor import BigOptionsProcessor, retry_on_api_error


class OptionMonitor:
    """港股期权大单监控器"""
    
    def __init__(self):
        self.logger = setup_logger()
        self.notifier = Notifier()
        self.data_handler = DataHandler()
        self.mac_notifier = MacNotifier()
        self.big_options_processor = BigOptionsProcessor()
        self.quote_ctx = None
        self.is_running = False
        self.monitor_thread = None
        self.subscribed_options = set()  # 已订阅的期权代码
        self.stock_price_cache = {}  # 股价缓存
        self.price_update_time = {}  # 股价更新时间
        self.option_chain_cache = {}  # 期权链缓存: {(owner_code, expiry_date): DataFrame}
        self.option_chain_cache_time = {}  # 期权链缓存时间
        self.stock_prices_file = os.path.join(os.path.dirname(DATA_CONFIG['csv_path']), 'stock_prices.json')
        self.option_chains_file = os.path.join(os.path.dirname(DATA_CONFIG['csv_path']), 'option_chains.json')
        self._last_option_chains_save = None  # 期权链缓存最近一次保存时间
        # 新增：基础信息文件（保存股票名称等基本不变字段）
        self.stock_base_info_file = os.path.join(os.path.dirname(DATA_CONFIG['csv_path']), 'stock_base_info.json')
        self.stock_base_info = {}
        
        # 加载缓存
        self._load_stock_prices_cache()
        self._load_option_chains_cache()
        
        # 初始化Futu连接
        self._init_futu_connection()
        
    # 新增：仅用非空字段更新的辅助方法
    def _merge_non_empty(self, dst: dict, src: dict) -> dict:
        if not isinstance(dst, dict):
            dst = {}
        if not isinstance(src, dict):
            return dst
        for k, v in src.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            dst[k] = v
        return dst

    # 新增：基础信息文件 读取/保存
    def _load_stock_base_info(self):
        try:
            if os.path.exists(self.stock_base_info_file):
                with open(self.stock_base_info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stocks = data.get('stocks') if isinstance(data, dict) else None
                if isinstance(stocks, dict):
                    self.stock_base_info = stocks
                elif isinstance(data, dict):
                    # 兼容平铺结构
                    self.stock_base_info = {k: v for k, v in data.items() if isinstance(v, dict)}
                else:
                    self.stock_base_info = {}
            else:
                # 若不存在，尝试从旧的 stock_prices.json 中抽取名称生成
                base = {}
                if os.path.exists(self.stock_prices_file):
                    try:
                        with open(self.stock_prices_file, 'r', encoding='utf-8') as f:
                            sp = json.load(f)
                        for code, info in (sp.get('prices') or {}).items():
                            if isinstance(info, dict):
                                name = info.get('name')
                                if name:
                                    base[code] = {'name': name}
                    except Exception:
                        pass
                self.stock_base_info = base
                # 立即落盘，便于后续使用
                self._save_stock_base_info()
        except Exception as e:
            self.logger.debug(f"加载基础信息失败(忽略): {e}")
            if not hasattr(self, 'stock_base_info') or self.stock_base_info is None:
                self.stock_base_info = {}

    def _save_stock_base_info(self):
        try:
            os.makedirs(os.path.dirname(self.stock_base_info_file), exist_ok=True)
            payload = {
                'update_time': datetime.now().isoformat(),
                'stocks': self.stock_base_info
            }
            with open(self.stock_base_info_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.debug(f"保存基础信息失败(忽略): {e}")

    def _load_stock_prices_cache(self):
        """从文件加载股价缓存"""
        try:
            # 先加载基础信息（如名称）
            self._load_stock_base_info()
            if os.path.exists(self.stock_prices_file):
                with open(self.stock_prices_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if 'prices' in data:
                    # 转换为内部缓存格式
                    for stock_code, stock_info in data['prices'].items():
                        # 统一为dict结构
                        if not isinstance(stock_info, dict):
                            stock_info = {'price': stock_info}
                        # 合并基础信息中的非空名称
                        base = self.stock_base_info.get(stock_code, {})
                        name_from_base = base.get('name') if isinstance(base, dict) else None
                        if name_from_base and not stock_info.get('name'):
                            stock_info['name'] = name_from_base
                        # 写入缓存
                        self.stock_price_cache[stock_code] = stock_info
                        # 将字符串时间转换为datetime对象
                        if 'update_time' in stock_info:
                            try:
                                update_time = datetime.fromisoformat(stock_info['update_time'])
                                self.price_update_time[stock_code] = update_time
                            except:
                                self.price_update_time[stock_code] = datetime.now()
                
                self.logger.info(f"已从文件加载 {len(self.stock_price_cache)} 只股票的价格缓存")
        except Exception as e:
            self.logger.warning(f"加载股价缓存失败: {e}")
    
    def _save_stock_prices_cache(self):
        """保存股价缓存到文件"""
        try:
            # 准备数据
            data = {
                'update_time': datetime.now().isoformat(),
                'prices': {}
            }
            
            # 转换内部缓存格式为JSON格式
            for stock_code, stock_info in self.stock_price_cache.items():
                if isinstance(stock_info, dict):
                    # 复制一份，避免修改原始数据
                    info_copy = stock_info.copy()
                    # 添加更新时间
                    if stock_code in self.price_update_time:
                        info_copy['update_time'] = self.price_update_time[stock_code].isoformat()
                    data['prices'][stock_code] = info_copy
                else:
                    # 兼容旧格式
                    data['prices'][stock_code] = {
                        'price': stock_info,
                        'name': '',
                        'update_time': datetime.now().isoformat()
                    }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.stock_prices_file), exist_ok=True)
            
            # 保存到文件
            with open(self.stock_prices_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"已保存 {len(self.stock_price_cache)} 只股票的价格缓存到文件")
        except Exception as e:
            self.logger.warning(f"保存股价缓存失败: {e}")
    
    def _load_option_chains_cache(self):
        """从文件加载期权链缓存"""
        try:
            if os.path.exists(self.option_chains_file):
                with open(self.option_chains_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.option_chain_cache = {}
                self.option_chain_cache_time = {}
                # 反序列化为内存结构：保持 DataFrame 为 DataFrame
                chains = data.get('chains', {})
                for key, payload in chains.items():
                    # key 形如 "HK.00700|2025-09-26"
                    records = payload.get('records', [])
                    ts = payload.get('update_time')
                    df = pd.DataFrame.from_records(records) if records else pd.DataFrame()
                    self.option_chain_cache[key] = df
                    if ts:
                        try:
                            self.option_chain_cache_time[key] = datetime.fromisoformat(ts)
                        except:
                            self.option_chain_cache_time[key] = datetime.now()
                self.logger.info(f"已从文件加载 {len(self.option_chain_cache)} 条期权链缓存")
        except Exception as e:
            self.logger.warning(f"加载期权链缓存失败: {e}")
    
    def _save_option_chains_cache(self, throttle_seconds: int = 10):
        """保存期权链缓存到文件（节流避免频繁写盘）"""
        try:
            now = datetime.now()
            if self._last_option_chains_save and (now - self._last_option_chains_save).total_seconds() < throttle_seconds:
                return
            data = {
                'update_time': now.isoformat(),
                'chains': {}
            }
            for key, df in self.option_chain_cache.items():
                if df is not None and not df.empty:
                    data['chains'][key] = {
                        'records': df.to_dict(orient='records'),
                        'update_time': (self.option_chain_cache_time.get(key, now)).isoformat()
                    }
                else:
                    data['chains'][key] = {
                        'records': [],
                        'update_time': (self.option_chain_cache_time.get(key, now)).isoformat()
                    }
            os.makedirs(os.path.dirname(self.option_chains_file), exist_ok=True)
            with open(self.option_chains_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_option_chains_save = now
            self.logger.debug(f"已保存 {len(self.option_chain_cache)} 条期权链缓存到文件")
        except Exception as e:
            self.logger.warning(f"保存期权链缓存失败: {e}")
    
    def _init_futu_connection(self):
        """初始化Futu OpenD连接"""
        try:
            self.quote_ctx = ft.OpenQuoteContext(
                host=str(FUTU_CONFIG['host']),
                port=int(FUTU_CONFIG['port'])
            )
            
            # 解锁交易仅适用于交易上下文(OpenHKTradeContext/USTrade/CNTrade)，行情上下文无需解锁
            
            # 设置股票报价处理器
            self.quote_ctx.set_handler(StockQuoteHandler(self))
            
            # 订阅监控股票的报价
            self._subscribe_stock_quotes(MONITOR_STOCKS)
                    
            self.logger.info("Futu OpenD连接成功")
            
        except Exception as e:
            self.logger.error(f"Futu OpenD连接失败: {e}")
            self.logger.error(traceback.format_exc())
            raise
    
    def _subscribe_stock_quotes(self, stock_codes):
        """订阅股票报价 - 只订阅尚未订阅的股票"""
        try:
            if not stock_codes:
                return
            
            # 跟踪已订阅的股票代码
            if not hasattr(self, 'subscribed_stocks'):
                self.subscribed_stocks = set()
            
            # 过滤出尚未订阅的股票
            new_stocks = [code for code in stock_codes if code not in self.subscribed_stocks]
            
            if not new_stocks:
                self.logger.debug("所有股票已订阅，无需重新订阅")
                return
                
            # 每次最多订阅50个，避免超出API限制
            batch_size = 50
            for i in range(0, len(new_stocks), batch_size):
                batch_codes = new_stocks[i:i+batch_size]
                
                # 订阅股票报价（移除不存在的SNAPSHOT类型）
                ret, data = self.quote_ctx.subscribe(batch_codes, [ft.SubType.QUOTE])
                if ret == ft.RET_OK:
                    self.logger.info(f"成功订阅 {len(batch_codes)} 只股票的报价+快照")
                    # 更新已订阅列表
                    self.subscribed_stocks.update(batch_codes)
                else:
                    self.logger.warning(f"订阅股票报价失败: {data}")
                
                # 避免API调用过于频繁
                time.sleep(0.5)
            
            # 订阅完成后校验覆盖情况（若有缺失，尝试再补订一次）
            try:
                missing = [c for c in MONITOR_STOCKS if c not in self.subscribed_stocks]
                if missing:
                    self.logger.warning(f"以下股票尚未订阅，尝试补订一次: {missing}")
                    try:
                        batch_size2 = 50
                        for i2 in range(0, len(missing), batch_size2):
                            batch_codes2 = missing[i2:i2+batch_size2]
                            ret2, data2 = self.quote_ctx.subscribe(batch_codes2, [ft.SubType.QUOTE])
                            if ret2 == ft.RET_OK:
                                self.subscribed_stocks.update(batch_codes2)
                                self.logger.info(f"补订成功 {len(batch_codes2)} 只股票")
                            else:
                                self.logger.warning(f"补订失败: {data2}")
                            time.sleep(0.2)
                        # 复核
                        missing2 = [c for c in MONITOR_STOCKS if c not in self.subscribed_stocks]
                        if missing2:
                            self.logger.warning(f"仍有未订阅股票(等待下一轮重试): {missing2}")
                        else:
                            self.logger.info("所有config中配置的股票已成功订阅(含补订)")
                    except Exception as _se:
                        self.logger.warning(f"补订过程中异常: {_se}")
                else:
                    self.logger.info("所有config中配置的股票均已订阅报价+快照")
            except Exception:
                pass
                
        except Exception as e:
            self.logger.error(f"订阅股票报价异常: {e}")
            self.logger.error(traceback.format_exc())
    
    @retry_on_api_error(max_retries=3, delay=5)
    def get_stock_price(self, stock_code: str) -> float:
        """获取股票当前价格（优先使用缓存）"""
        try:
            # 检查缓存是否有效
            if stock_code in self.stock_price_cache and stock_code in self.price_update_time:
                cache_time = self.price_update_time[stock_code]
                if (datetime.now() - cache_time).seconds < 600:  # 缓存10分钟内有效
                    cached = self.stock_price_cache[stock_code]
                    self.logger.debug(f"使用缓存的股价: {stock_code} = {cached}")
                    # 兼容两种缓存结构：float 或 {'price': x, 'name': y}
                    if isinstance(cached, dict):
                        return cached.get('price', 0.0)
                    return cached
            
            # 缓存无效，获取实时股价
            ret_snap, snap_data = self.quote_ctx.get_market_snapshot([stock_code])
            if ret_snap == ft.RET_OK and not snap_data.empty:
                # 提取行数据并尽量补齐成交额/量/名称
                row0 = snap_data.iloc[0]
                price = float(row0.get('last_price'))
                info = {'price': price}
                try:
                    tv = row0.get('turnover', None)
                    if tv is not None:
                        info['turnover'] = float(tv)
                except Exception:
                    pass
                try:
                    vol0 = row0.get('volume', None)
                    if vol0 is not None:
                        info['volume'] = int(vol0)
                except Exception:
                    pass
                try:
                    nm0 = row0.get('name', None)
                    if nm0 and str(nm0).strip():
                        info['name'] = str(nm0)
                except Exception:
                    pass
                # 若名称仍缺，从基础信息补齐
                try:
                    if 'name' not in info:
                        base = self.stock_base_info.get(stock_code, {})
                        if isinstance(base, dict) and base.get('name'):
                            info['name'] = base['name']
                except Exception:
                    pass
                self.stock_price_cache[stock_code] = info
                self.price_update_time[stock_code] = datetime.now()
                
                # 定期保存股价缓存到文件
                if len(self.stock_price_cache) % 5 == 0:  # 每更新5个股价保存一次
                    self._save_stock_prices_cache()
                self.logger.debug(f"获取实时股价: {stock_code} = {price}, 成交额={info.get('turnover', '')}, 成交量={info.get('volume', '')}")
                return price
            else:
                self.logger.warning(f"获取{stock_code}股价失败")
                
                # 如果缓存中有旧数据，返回旧数据
                if stock_code in self.stock_price_cache:
                    cached_val = self.stock_price_cache[stock_code]
                    self.logger.debug(f"使用旧缓存的股价: {stock_code} = {cached_val}")
                    return (cached_val.get('price', 0.0) if isinstance(cached_val, dict) else float(cached_val or 0.0))
                
                # 从本地缓存文件回退
                try:
                    if os.path.exists(self.stock_prices_file):
                        with open(self.stock_prices_file, 'r', encoding='utf-8') as f:
                            sp = json.load(f)
                        prices = sp.get('prices') if isinstance(sp, dict) else {}
                        info = prices.get(stock_code) if isinstance(prices, dict) else None
                        if isinstance(info, dict) and 'price' in info:
                            self.logger.info(f"使用文件缓存股价: {stock_code} = {info['price']}")
                            # 同步到内存缓存
                            self.stock_price_cache[stock_code] = info
                            self.price_update_time[stock_code] = datetime.now()
                            return float(info['price'])
                        elif isinstance(info, (int, float)):
                            self.logger.info(f"使用文件缓存股价: {stock_code} = {info}")
                            self.stock_price_cache[stock_code] = {'price': float(info)}
                            self.price_update_time[stock_code] = datetime.now()
                            return float(info)
                except Exception as _e:
                    self.logger.debug(f"读取文件缓存失败(忽略): {_e}")
                
                self.logger.info(f"使用兜底默认股价: {stock_code} = 100.0")
                return 100.0
                
        except Exception as e:
            self.logger.error(f"获取{stock_code}股价异常: {e}")
            self.logger.error(traceback.format_exc())
            
            # 如果缓存中有旧数据，返回旧数据
            if stock_code in self.stock_price_cache:
                return self.stock_price_cache[stock_code]
            
            return 100.0  # 默认价格
    
    @retry_on_api_error(max_retries=3, delay=5)
    def get_stock_options(self, stock_code: str) -> List[str]:
        """获取指定股票的期权合约列表"""
        try:
            # 获取当前股价，用于筛选合适的期权
            current_price = self.get_stock_price(stock_code)
            self.logger.info(f"{stock_code}当前股价: {current_price}")
            
            # 计算价格范围（上下20%）
            price_range = OPTION_FILTER.get('price_range', 0.2)
            price_lower = current_price * (1 - price_range)
            price_upper = current_price * (1 + price_range)
            
            # 使用API获取期权到期日
            ret, data = self.quote_ctx.get_option_expiration_date(stock_code)
            if ret != ft.RET_OK:
                self.logger.error(f"获取{stock_code}期权到期日失败: {data}")
                return []
            
            # 只获取最近的几个到期日（减少API调用）
            recent_dates = data.head(3)  # 最近的3个到期日
            
            option_codes = []
            # 获取每个到期日的期权合约
            for _, row in recent_dates.iterrows():
                # 使用正确的列名获取到期日（兼容不同版本的API）
                expiry_date = row.get('strike_time', row.get('expiry_date'))
                if not expiry_date:
                    self.logger.warning(f"无法获取到期日信息: {row}")
                    continue
                try:
                    # 判断是否为指数期权
                    index_option_type = ft.IndexOptionType.INDEX if stock_code.endswith('.HSI') else ft.IndexOptionType.NORMAL
                    
                    # 使用完整参数获取期权链，包括价格筛选
                    ret2, option_data = self.quote_ctx.get_option_chain(
                        code=stock_code,
                        start=expiry_date,
                        end=expiry_date,
                        option_type=ft.OptionType.ALL,
                        option_cond_type=ft.OptionCondType.ALL,
                        index_option_type=index_option_type
                    )
                    
                    if ret2 == ft.RET_OK and not option_data.empty:
                        # 筛选执行价格在当前股价上下范围内的期权
                        filtered_options = option_data[
                            (option_data['strike_price'] >= price_lower) & 
                            (option_data['strike_price'] <= price_upper)
                        ]
                        
                        # 直接使用价格筛选后的期权
                        if not filtered_options.empty:
                            # 如果没有活跃期权，使用价格范围内的所有期权
                            option_codes.extend(filtered_options['code'].tolist())
                            self.logger.debug(f"{stock_code} {expiry_date}到期的期权中有{len(filtered_options)}个在价格范围内")
                        else:
                            # 如果没有在范围内的，取最接近当前价格的几个
                            option_data['price_diff'] = abs(option_data['strike_price'] - current_price)
                            closest_options = option_data.nsmallest(5, 'price_diff')
                            option_codes.extend(closest_options['code'].tolist())
                            self.logger.debug(f"{stock_code} {expiry_date}添加5个最接近当前价格的期权")
                        
                        # 记录一些有用的期权信息，如隐含波动率
                        if 'implied_volatility' in option_data.columns:
                            avg_iv = option_data['implied_volatility'].mean()
                            self.logger.debug(f"{stock_code} {expiry_date}期权平均隐含波动率: {avg_iv:.2f}%")
                except Exception as e:
                    self.logger.warning(f"获取{stock_code} {expiry_date}期权链异常: {e}")
                    continue
            
            self.logger.debug(f"{stock_code} 期权合约数量: {len(option_codes)}")
            return option_codes
            
        except Exception as e:
            self.logger.error(f"获取{stock_code}期权合约异常: {e}")
            self.logger.error(traceback.format_exc())
            return []

    
    @retry_on_api_error(max_retries=3, delay=5)
    def get_option_trades(self, option_code: str) -> Optional[pd.DataFrame]:
        """获取期权逐笔交易数据"""
        try:
            # 首先获取期权的基本信息
            # 兼容：不再调用 get_option_info，改为从代码解析 + 快照补充
            try:
                # 使用big_options_processor中的方法解析期权代码
                strike_price = self.big_options_processor._parse_strike_from_code(option_code)
                # 基于末尾 C/P 的相对位置判断类型，避免被标的简称中的字母误伤
                option_type = ('Call' if option_code.rfind('C') > option_code.rfind('P') else 'Put') if ('C' in option_code or 'P' in option_code) else '未知'
                expiry_date = self.big_options_processor._parse_expiry_from_code(option_code)
                option_info = {
                    'strike_price': strike_price,
                    'option_type': option_type,
                    'expiry_date': expiry_date
                }
                # 兜底：若解析信息缺失，尝试用快照/期权链补齐，避免执行价=0或类型未知
                try:
                    if (not option_info.get('strike_price')) or option_info.get('option_type') in ('未知', None) or not option_info.get('expiry_date'):
                        owner_code = None
                        # 先尝试快照补齐
                        ret_s2, s2 = self.quote_ctx.get_market_snapshot([option_code])
                        if ret_s2 == ft.RET_OK and s2 is not None and not s2.empty:
                            row2 = s2.iloc[0]
                            # 部分环境下快照可能提供执行价/类型
                            if 'strike_price' in s2.columns:
                                try:
                                    sp = float(row2.get('strike_price') or 0)
                                    if sp > 0:
                                        option_info['strike_price'] = sp
                                except Exception:
                                    pass
                            if 'option_type' in s2.columns and row2.get('option_type') in ('Call', 'Put'):
                                option_info['option_type'] = row2.get('option_type')
                            # 记录正股代码供链路映射
                            owner_code = row2.get('owner_stock_code') or row2.get('owner_code')
                        # 若仍无执行价且拥有正股代码与到期日，则用期权链映射获取准确执行价（带缓存）
                        if (not option_info.get('strike_price')) and owner_code and option_info.get('expiry_date'):
                            date_str = option_info['expiry_date']
                            cache_key = (owner_code, date_str)
                            current_time = datetime.now()
                            
                            # 检查缓存（5分钟有效）
                            oc_df = None
                            if (cache_key in self.option_chain_cache and 
                                cache_key in self.option_chain_cache_time and
                                (current_time - self.option_chain_cache_time[cache_key]).seconds < 300):
                                oc_df = self.option_chain_cache[cache_key]
                                self.logger.debug(f"使用缓存的期权链: {cache_key}")
                            else:
                                # 获取新的期权链数据
                                ret_oc, oc_df = self.quote_ctx.get_option_chain(owner_code, date_str)
                                if ret_oc == ft.RET_OK and oc_df is not None and not oc_df.empty:
                                    # 更新缓存
                                    self.option_chain_cache[cache_key] = oc_df
                                    self.option_chain_cache_time[cache_key] = current_time
                                    self.logger.debug(f"缓存期权链数据: {cache_key}, {len(oc_df)}个期权")
                                    # 持久化期权链缓存
                                    try:
                                        self._save_option_chains_cache()
                                    except Exception as _e:
                                        self.logger.debug(f"保存期权链缓存失败(略过): {_e}")
                            
                            # 从期权链中查找匹配的期权代码
                            if oc_df is not None and not oc_df.empty:
                                match_df = oc_df[oc_df['code'] == option_code]
                                if not match_df.empty:
                                    sp2 = float(match_df.iloc[0].get('strike_price') or 0)
                                    if sp2 > 0:
                                        option_info['strike_price'] = sp2
                                        self.logger.debug(f"从期权链获取执行价: {option_code} = {sp2}")
                except Exception:
                    # 兜底失败不影响主流程
                    pass
                # 若有正股代码则补充正股价差信息
                try:
                    ret_stock, stock_snap = self.quote_ctx.get_market_snapshot([stock_code]) if hasattr(self, 'quote_ctx') else (-1, None)
                    if ret_stock == ft.RET_OK and stock_snap is not None and not stock_snap.empty:
                        current_stock_price = float(stock_snap.iloc[0]['last_price'])
                        price_diff = strike_price - current_stock_price if current_stock_price else 0
                        price_diff_pct = (price_diff / current_stock_price) * 100 if current_stock_price else 0
                        option_info['stock_price'] = current_stock_price
                        option_info['price_diff'] = price_diff
                        option_info['price_diff_pct'] = price_diff_pct
                except Exception:
                    pass
            except Exception:
                option_info = {'strike_price': 0, 'option_type': '未知', 'expiry_date': ''}
                self.logger.debug(f"期权{option_code}基本信息: 执行价={option_info.iloc[0].get('strike_price', 0)}, 类型={option_info.iloc[0].get('option_type', '未知')}")
            
            # 使用API获取逐笔交易数据
            ret, data = self.quote_ctx.get_rt_ticker(option_code)
            if ret != ft.RET_OK:
                self.logger.debug(f"获取{option_code}交易数据失败: {data}")
                
                # 如果逐笔交易获取失败，尝试获取市场快照
                ret_snap, snap_data = self.quote_ctx.get_market_snapshot([option_code])
                if ret_snap == ft.RET_OK and not snap_data.empty:
                    # 从快照中提取成交量和成交额
                    row = snap_data.iloc[0]
                    volume = row.get('volume', 0)
                    turnover = row.get('turnover', 0)
                    
                    # 检查是否符合大单条件
                    if (volume >= OPTION_FILTER['min_volume'] and 
                        turnover >= OPTION_FILTER['min_turnover']):
                        
                        # 创建一个模拟的逐笔交易数据
                        mock_data = pd.DataFrame([{
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'price': row.get('last_price', 0),
                            'volume': volume,
                            'turnover': turnover,
                            'direction': 'Unknown'
                        }])
                        
                        # 添加期权代码
                        mock_data['option_code'] = option_code
                        mock_data['timestamp'] = datetime.now()
                        
                        return mock_data
                
                return None
            
            if data.empty:
                return None
                
            # 筛选大单交易
            filtered_data = self._filter_large_trades(data, option_code)
            return filtered_data
            
        except Exception as e:
            self.logger.error(f"获取{option_code}交易数据异常: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    def _filter_large_trades(self, trades_df: pd.DataFrame, option_code: str) -> pd.DataFrame:
        """筛选大单交易"""
        if trades_df.empty:
            return trades_df
        
        # 应用筛选条件
        # 确保volume字段存在
        if "volume" not in trades_df.columns:
            self.logger.warning(f"trades_df中不存在volume字段，无法筛选大单")
            return pd.DataFrame()
        
        mask = (
            (trades_df['volume'] >= OPTION_FILTER['min_volume']) &
            (trades_df['turnover'] >= OPTION_FILTER['min_turnover'])
        )
        
        large_trades = trades_df[mask].copy()
        
        if not large_trades.empty:
            large_trades['option_code'] = option_code
            large_trades['timestamp'] = datetime.now()
            
        return large_trades
    
    def monitor_single_stock(self, stock_code: str):
        """监控单个股票的期权大单"""
        try:
            # 获取期权合约列表
            option_codes = self.get_stock_options(stock_code)
            if not option_codes:
                return
            
            all_large_trades = []
            
            # 监控每个期权合约
            for option_code in option_codes:
                large_trades = self.get_option_trades(option_code)
                if large_trades is not None and not large_trades.empty:
                    all_large_trades.append(large_trades)
            
            # 处理发现的大单交易
            if all_large_trades:
                combined_trades = pd.concat(all_large_trades, ignore_index=True)
                self._process_large_trades(stock_code, combined_trades)
                
        except Exception as e:
            self.logger.error(f"监控{stock_code}异常: {e}")
            self.logger.error(traceback.format_exc())
    
    def _process_large_trades(self, stock_code: str, trades_df: pd.DataFrame):
        """处理发现的大单交易"""
        for _, trade in trades_df.iterrows():
            # 规范化成交时间
            try:
                t_str = str(trade.get('time', ''))
                if (len(t_str) >= 10 and ('-' in t_str or '/' in t_str)):
                    time_full = t_str.split('.')[0]
                else:
                    time_full = f"{datetime.now().strftime('%Y-%m-%d')} {t_str}"
            except Exception:
                time_full = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            trade_info = {
                'stock_code': stock_code,
                'option_code': trade['option_code'],
                'time': trade['time'],
                'time_full': time_full,
                'price': trade['price'],
                'volume': trade['volume'],
                'turnover': trade['turnover'],
                'direction': trade.get('direction', 'Unknown'),
                'timestamp': trade['timestamp']
            }
            
            # 发送通知
            self.notifier.send_notification(trade_info)
            
            # 保存数据
            self.data_handler.save_trade(trade_info)
            
            self.logger.info(f"发现大单: {stock_code} {trade_info}")
    
    def _is_trading_time(self) -> bool:
        """检查是否在交易时间内"""
        now = datetime.now().time()
        start_time = datetime.strptime(MONITOR_TIME['start_time'], '%H:%M:%S').time()
        end_time = datetime.strptime(MONITOR_TIME['end_time'], '%H:%M:%S').time()
        
        return start_time <= now <= end_time
    
    def _monitor_loop(self):
        """监控主循环 - 1分钟执行一次完整大单汇总"""
        self.logger.info("开始1分钟间隔监控港股期权大单交易（每次执行完整大单汇总）")
        
        # 设置期权推送回调
        self.quote_ctx.set_handler(OptionTickerHandler(self))
        
        # 初始化股票报价订阅
        self._subscribe_stock_quotes(MONITOR_STOCKS)
        
        # 初始化订阅更新计数器
        subscription_update_counter = 0
        
        while self.is_running:
            try:
                # 每分钟执行一次完整的大单汇总
                self.logger.info("执行完整大单汇总...")
                self._hourly_big_options_check()
                
                # 每5分钟更新一次期权订阅列表
                subscription_update_counter += 1
                if subscription_update_counter >= 5:
                    self.logger.info("定期更新期权订阅列表...")
                    self._update_option_subscriptions()
                    subscription_update_counter = 0
                
                # 等待下一次监控 (1分钟)
                time.sleep(MONITOR_TIME['interval'])
                
            except KeyboardInterrupt:
                self.logger.info("收到停止信号")
                break
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                self.logger.error(traceback.format_exc())
                time.sleep(10)  # 异常后等待10秒再继续
    
    def _quick_options_check(self):
        """快速期权检查 - 1分钟间隔"""
        try:
            if not self._is_trading_time():
                return
            
            # 检查连接状态
            if not self.quote_ctx:
                return
            
            # 只检查前3个股票，避免API调用过于频繁
            quick_stocks = MONITOR_STOCKS[:3]
            
            for stock_code in quick_stocks:
                if not self.is_running:
                    break
                    
                try:
                    # 获取少量期权合约进行快速检查
                    option_codes = self.get_stock_options(stock_code)
                    
                    if option_codes:
                        # 只检查前5个最活跃的期权
                        check_codes = option_codes[:5]
                        
                        # 订阅这些期权的逐笔推送
                        self._subscribe_options(check_codes)
                        
                        # 同时进行主动检查
                        for option_code in check_codes:
                            trades_df = self.get_option_trades(option_code)
                            if trades_df is not None and not trades_df.empty:
                                # 发现大单，立即通知
                                for _, trade in trades_df.iterrows():
                                    # 规范化成交时间
                                    try:
                                        t_str = str(trade.get('time', ''))
                                        if (len(t_str) >= 10 and ('-' in t_str or '/' in t_str)):
                                            time_full = t_str.split('.')[0]
                                        else:
                                            time_full = f"{datetime.now().strftime('%Y-%m-%d')} {t_str}"
                                    except Exception:
                                        time_full = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                    trade_info = {
                                        'stock_code': stock_code,
                                        'option_code': trade['option_code'],
                                        'time': trade['time'],
                                        'time_full': time_full,
                                        'price': trade['price'],
                                        'volume': trade['volume'],
                                        'turnover': trade['turnover'],
                                        'direction': trade.get('direction', 'Unknown'),
                                        'timestamp': trade['timestamp']
                                    }
                                    
                                    self.notifier.send_notification(trade_info)
                                    self.data_handler.save_trade(trade_info)
                                
                                self.logger.info(f"快速检查发现 {len(trades_df)} 笔大单: {stock_code} - {option_code}")
                                
                except Exception as e:
                    self.logger.debug(f"快速检查{stock_code}失败: {e}")
                    self.logger.debug(traceback.format_exc())
                    
        except Exception as e:
            self.logger.error(f"快速期权检查失败: {e}")
            self.logger.error(traceback.format_exc())
    
    def _hourly_big_options_check(self):
        """完整大单期权检查（每分钟执行一次）"""
        try:
            self.logger.info("开始执行完整大单期权检查...")
            
            # 检查连接状态
            if not self.quote_ctx:
                self.logger.error("Futu连接已断开，尝试重新连接...")
                self._init_futu_connection()
                if not self.quote_ctx:
                    self.logger.error("重新连接失败，跳过本次检查")
                    return
            
            # 先获取所有监控股票的当前股价，确保股价缓存是最新的
            self.logger.info("预先获取所有监控股票的当前股价...")
            for stock_code in MONITOR_STOCKS:
                try:
                    current_price = self.get_stock_price(stock_code)
                    self.logger.info(f"{stock_code}当前股价: {current_price}")
                except Exception as e:
                    self.logger.error(f"获取{stock_code}股价失败: {e}")
            
            # 获取最近2天的大单期权，传递self作为option_monitor参数，共用股价信息
            big_options = self.big_options_processor.get_recent_big_options(
                self.quote_ctx, MONITOR_STOCKS, option_monitor=self
            )
            
            if big_options:
                self.logger.info(f"发现 {len(big_options)} 笔大单期权交易")
                
                # 保存汇总数据
                self.big_options_processor.save_big_options_summary(big_options)
                
                # 发送Mac通知
                if NOTIFICATION.get('enable_mac_notification', False):
                    try:
                        self.mac_notifier.send_big_options_summary(big_options)
                    except Exception as e:
                        self.logger.warning(f"Mac通知发送失败: {e}")
                
                # 发送企业微信通知
                if NOTIFICATION.get('enable_wework_bot', False):
                    try:
                        self.notifier.send_big_options_summary(big_options)
                    except Exception as e:
                        self.logger.warning(f"企业微信汇总通知发送失败: {e}")
                
                # 控制台通知
                if NOTIFICATION.get('enable_console', True):
                    self._print_big_options_summary(big_options)
                
            else:
                self.logger.info("未发现符合条件的大单期权交易")
                # 仍然保存空的汇总，更新时间戳
                self.big_options_processor.save_big_options_summary([])
                
        except Exception as e:
            self.logger.error(f"每小时大单检查失败: {e}")
            self.logger.error(traceback.format_exc())
    
    def _print_big_options_summary(self, big_options: List[Dict]):
        """打印大单期权汇总"""
        print("\n" + "="*60)
        print(f"🚨 港股期权大单汇总 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*60)
        
        # 过滤出符合min_volume要求的交易
        filtered_options = []
        for opt in big_options:
            stock_code = opt.get('stock_code', 'Unknown')
            volume_diff = opt.get('volume_diff', 0)
            
            # 获取该股票的配置
            option_filter = get_option_filter(stock_code)
            min_volume = option_filter.get('min_volume', 10)
            
            # 只有增加的交易量>=min_volume才显示
            if volume_diff >= min_volume:
                filtered_options.append(opt)
        
        total_turnover = sum(opt.get('turnover', 0) for opt in big_options)
        filtered_turnover = sum(opt.get('turnover', 0) for opt in filtered_options)
        print(f"📊 总计: {len(big_options)} 笔大单，总金额: {total_turnover/10000:.1f}万港币")
        print(f"📋 符合通知条件: {len(filtered_options)} 笔，金额: {filtered_turnover/10000:.1f}万港币")
        
        # 按股票分组显示（使用过滤后的期权）
        stock_groups = {}
        for opt in filtered_options:
            stock_code = opt.get('stock_code', 'Unknown')
            if stock_code not in stock_groups:
                stock_groups[stock_code] = []
            stock_groups[stock_code].append(opt)
        
        # 按成交额排序股票
        sorted_stocks = sorted(stock_groups.items(), 
                              key=lambda x: sum(opt.get('turnover', 0) for opt in x[1]), 
                              reverse=True)
        
        for stock_code, options in sorted_stocks:
            stock_turnover = sum(opt.get('turnover', 0) for opt in options)
            # 获取股票名称（优先从期权数据，其次从缓存补齐）
            stock_name = options[0].get('stock_name', '') if options else ''
            if not stock_name:
                cached = self.stock_price_cache.get(stock_code)
                if isinstance(cached, dict):
                    stock_name = cached.get('name', '') or stock_name
            stock_display = f"{stock_name} ({stock_code})" if stock_name else stock_code
            print(f"\n📈 {stock_display}: {len(options)}笔 {stock_turnover/10000:.1f}万港币")
            
            # 显示前3笔最大的交易
            top_options = sorted(options, key=lambda x: x.get('turnover', 0), reverse=True)[:3]
            for i, opt in enumerate(top_options, 1):
                # 选择展示时间：优先 time_full，其次 time，最后 timestamp
                show_time = opt.get('time_full') or opt.get('time')
                if not show_time and opt.get('timestamp'):
                    try:
                        show_time = opt['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        show_time = ''
                time_suffix = f" 成交时间: {show_time}" if show_time else ""

                # 解析期权类型
                option_type = self._parse_option_type(opt.get('option_code', ''))
                
                # 添加买卖方向显示
                direction = opt.get('direction', 'Unknown')
                direction_text = ""
                if direction == "BUY":
                    direction_text = "买入"
                elif direction == "SELL":
                    direction_text = "卖出"
                elif direction == "NEUTRAL":
                    direction_text = "中性"
                
                direction_display = f", {direction_text}" if direction_text else ""
                
                # 添加变化量信息
                volume_diff = opt.get('volume_diff', 0)
                if volume_diff > 0:
                    diff_text = f", +{volume_diff}张"
                elif volume_diff < 0:
                    diff_text = f", {volume_diff}张"
                else:
                    diff_text = ""
                
                price = opt.get('price', opt.get('last_price', 0))
                volume = opt.get('volume', 0)
                turnover = opt.get('turnover', 0)
                
                print(
                    f"   {i}. {opt.get('option_code', 'N/A')}: {option_type}{direction_display}, "
                    f"{price:.3f}×{volume}张{diff_text}, {turnover/10000:.1f}万{time_suffix}"
                )
        
        print("="*60 + "\n")
    
    def _parse_option_type(self, option_code: str) -> str:
        """解析期权类型 (Call/Put)"""
        import re
        
        if not option_code:
            return "Unknown"

        try:
            if option_code.startswith('HK.'):
                code_part = option_code[3:]  # 去掉 HK.
                # 规则：匹配两段数字之间的单个 C 或 P，例如 ...250929P102500
                m = re.search(r'\d+([CP])\d+', code_part)
                if m:
                    return 'Call (看涨)' if m.group(1) == 'C' else 'Put (看跌)'
        except Exception as e:
            self.logger.debug(f"解析期权类型失败: {e}")
        
        return "Unknown"
    
    def start_monitoring(self):
        """启动监控"""
        if self.is_running:
            self.logger.warning("监控已在运行中")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info("期权大单监控已启动")
    
    def _subscribe_options(self, option_codes):
        """订阅期权的逐笔推送"""
        try:
            # 过滤出尚未订阅的期权
            new_codes = [code for code in option_codes if code not in self.subscribed_options]
            
            if not new_codes:
                return
                
            # 每次最多订阅5个，避免超出API限制
            batch_size = 5
            for i in range(0, len(new_codes), batch_size):
                batch_codes = new_codes[i:i+batch_size]
                
                # 订阅逐笔推送
                ret, data = self.quote_ctx.subscribe(batch_codes, [ft.SubType.TICKER])
                if ret == ft.RET_OK:
                    self.logger.debug(f"成功订阅 {len(batch_codes)} 个期权的逐笔推送")
                    # 更新已订阅列表
                    self.subscribed_options.update(batch_codes)
                else:
                    self.logger.warning(f"订阅期权推送失败: {data}")
                
                # 避免API调用过于频繁
                time.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"订阅期权推送异常: {e}")
            self.logger.error(traceback.format_exc())
    
    def _update_option_subscriptions(self):
        """更新期权订阅列表 - 智能更新，避免不必要的取消订阅"""
        try:
            # 获取最活跃的期权进行订阅
            active_options = []
            
            for stock_code in MONITOR_STOCKS[:5]:  # 只处理前5个股票
                try:
                    option_codes = self.get_stock_options(stock_code)
                    if option_codes:
                        # 每个股票取前5个期权
                        active_options.extend(option_codes[:5])
                except Exception as e:
                    self.logger.debug(f"获取{stock_code}期权失败: {e}")
                    self.logger.debug(traceback.format_exc())
            
            # 计算需要新增和需要取消的订阅
            active_options_set = set(active_options)
            
            # 需要新增的订阅
            new_options = [code for code in active_options if code not in self.subscribed_options]
            
            # 需要取消的订阅
            obsolete_options = [code for code in self.subscribed_options if code not in active_options_set]
            
            # 取消不再需要的期权订阅
            if obsolete_options:
                try:
                    # 每次最多取消50个，避免API限制
                    batch_size = 50
                    for i in range(0, len(obsolete_options), batch_size):
                        batch_codes = obsolete_options[i:i+batch_size]
                        ret, data = self.quote_ctx.unsubscribe(batch_codes, [ft.SubType.TICKER])
                        if ret == ft.RET_OK:
                            self.logger.info(f"已取消 {len(batch_codes)} 个期权的订阅")
                            # 更新已订阅列表
                            for code in batch_codes:
                                if code in self.subscribed_options:
                                    self.subscribed_options.remove(code)
                        else:
                            self.logger.warning(f"取消期权订阅失败: {data}")
                        
                        # 避免API调用过于频繁
                        time.sleep(0.5)
                except Exception as e:
                    self.logger.warning(f"取消期权订阅异常: {e}")
                    self.logger.warning(traceback.format_exc())
            
            # 订阅新的期权
            if new_options:
                self._subscribe_options(new_options)
            else:
                self.logger.debug("没有新的期权需要订阅")
            
        except Exception as e:
            self.logger.error(f"更新期权订阅异常: {e}")
            self.logger.error(traceback.format_exc())
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        if self.quote_ctx:
            # 取消所有订阅
            try:
                self.quote_ctx.unsubscribe_all()
                self.logger.info("已取消所有订阅")
            except Exception as e:
                self.logger.warning(f"取消订阅异常: {e}")
            
            # 关闭连接
            self.quote_ctx.close()
        
        self.logger.info("期权大单监控已停止")
    
    def get_monitoring_status(self) -> Dict:
        """获取监控状态"""
        return {
            'is_running': self.is_running,
            'monitored_stocks': MONITOR_STOCKS,
            'subscribed_stocks': list(self.subscribed_stocks) if hasattr(self, 'subscribed_stocks') else [],
            'missing_subscriptions': [c for c in MONITOR_STOCKS if not hasattr(self, 'subscribed_stocks') or c not in self.subscribed_stocks],
            'filter_conditions': OPTION_FILTER,
            'trading_time': self._is_trading_time()
        }


def signal_handler(signum, frame):
    """信号处理器"""
    print("\n收到停止信号，正在关闭监控...")
    if 'monitor' in globals():
        monitor.stop_monitoring()
    sys.exit(0)


# 股票报价处理器
class StockQuoteHandler(ft.StockQuoteHandlerBase):
    """股票报价推送处理器"""
    
    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor
        self.logger = monitor.logger
    
    def on_recv_rsp(self, rsp_pb):
        """收到报价推送回调"""
        ret_code, data = super().on_recv_rsp(rsp_pb)
        if ret_code != ft.RET_OK:
            self.logger.error(f"股票报价推送错误: {data}")
            return ret_code, data
        
        # 处理推送数据
        if data.empty:
            return ret_code, data
        
        # 更新股价缓存（含成交额/名称）
        for _, row in data.iterrows():
            stock_code = row['code']
            last_price = row['last_price']
            turnover = row.get('turnover', None)
            stock_name = row.get('name', '') if isinstance(row, dict) or hasattr(row, 'get') else ''
            
            # 取已有缓存，统一存储为dict结构
            prev = self.monitor.stock_price_cache.get(stock_code, {})
            if not isinstance(prev, dict):
                prev = {}
            info = dict(prev)  # 复制避免原地修改副作用
            info['price'] = last_price
            if turnover is not None:
                try:
                    info['turnover'] = float(turnover)
                except Exception:
                    pass
            # 记录成交量（如推送包含）
            try:
                vol = row.get('volume', None)
                if vol is not None:
                    info['volume'] = int(vol)
            except Exception:
                pass
            if stock_name and not info.get('name'):
                info['name'] = stock_name
            
            # 更新缓存与时间
            self.monitor.stock_price_cache[stock_code] = info
            self.monitor.price_update_time[stock_code] = datetime.now()

            # 更新基础信息文件（仅用非空值合并）
            try:
                if stock_name:
                    prev_base = self.monitor.stock_base_info.get(stock_code, {})
                    merged = dict(prev_base) if isinstance(prev_base, dict) else {}
                    if stock_name and (merged.get('name') != stock_name):
                        merged['name'] = stock_name
                        self.monitor.stock_base_info[stock_code] = merged
                        self.monitor._save_stock_base_info()
            except Exception:
                pass
            
            # 记录股价变动
            self.logger.debug(f"股价更新: {stock_code} 价格={last_price}, 成交额={info.get('turnover', '')}, 成交量={info.get('volume', '')}")
        
        return ret_code, data


# 期权行情推送处理器
class OptionTickerHandler(ft.TickerHandlerBase):
    """期权逐笔成交推送处理器"""
    
    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor
        self.logger = monitor.logger
    
    def on_recv_rsp(self, rsp_pb):
        """收到逐笔推送回调"""
        ret_code, data = super().on_recv_rsp(rsp_pb)
        if ret_code != ft.RET_OK:
            self.logger.error(f"期权逐笔推送错误: {data}")
            return ret_code, data
        
        # 处理推送数据
        if data.empty:
            return ret_code, data
        
        # 获取期权代码
        option_code = data['code'].iloc[0]
        
        # 筛选大单
        for _, row in data.iterrows():
            volume = row.get("volume", 0)
            turnover = row.get("price", 0) * volume
            
            # 检查是否符合大单条件
            if volume >= OPTION_FILTER['min_volume'] and turnover >= OPTION_FILTER['min_turnover']:
                self.logger.info(f"🔔 推送发现大单: {option_code}, 成交量: {volume}, 成交额: {turnover:.2f}")
                
                # 规范化成交时间
                try:
                    t_str = str(row.get('time', ''))
                    if (len(t_str) >= 10 and ('-' in t_str or '/' in t_str)):
                        time_full = t_str.split('.')[0]
                    else:
                        time_full = f"{datetime.now().strftime('%Y-%m-%d')} {t_str}"
                except Exception:
                    time_full = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 构建交易信息
                trade_info = {
                    'option_code': option_code,
                    'time': row['time'],
                    'time_full': time_full,
                    'price': row['price'],
                    'volume': volume,
                    'turnover': turnover,
                    'direction': row.get('ticker_direction', 'Unknown'),
                    'timestamp': datetime.now()
                }
                
                # 获取对应的股票代码
                stock_code = self._extract_stock_code(option_code)
                if stock_code:
                    trade_info['stock_code'] = stock_code
                    
                    # 发送通知
                    self.monitor.notifier.send_notification(trade_info)
                    
                    # 保存数据
                    self.monitor.data_handler.save_trade(trade_info)
        
        return ret_code, data
    
    def _extract_stock_code(self, option_code):
        """从期权代码提取股票代码"""
        try:
            # 期权代码格式通常为 HK.00700C2309A
            if option_code.startswith('HK.'):
                # 提取股票代码部分
                parts = option_code[3:].split('C')
                if len(parts) > 1:
                    stock_code = parts[0]
                    return f"HK.{stock_code}"
                
                parts = option_code[3:].split('P')
                if len(parts) > 1:
                    stock_code = parts[0]
                    return f"HK.{stock_code}"
            
            return None
        except:
            return None


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建必要的目录
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    try:
        # 创建监控器实例
        global monitor
        monitor = OptionMonitor()
        
        # 启动监控
        monitor.start_monitoring()
        
        # 保持程序运行
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"程序启动失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()