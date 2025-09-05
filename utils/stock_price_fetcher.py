# -*- coding: utf-8 -*-
"""
股价获取器
使用futuapi获取实时股价
"""

import futu as ft
import logging
from datetime import datetime
from typing import Dict, Optional


class StockPriceFetcher:
    """股价获取器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.StockPriceFetcher')
        self.price_cache = {}  # 股价缓存
        self.cache_time = {}   # 缓存时间
        self.quote_ctx = None
        
    def connect(self):
        """连接到富途API"""
        try:
            if self.quote_ctx is None:
                self.quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
                self.logger.info("成功连接到富途API")
            return True
        except Exception as e:
            self.logger.error(f"连接富途API失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.quote_ctx:
            self.quote_ctx.close()
            self.quote_ctx = None
            self.logger.info("已断开富途API连接")
    
    def get_stock_price(self, stock_code: str) -> float:
        """获取股票当前价格"""
        try:
            # 检查缓存（5分钟内有效）
            current_time = datetime.now()
            cache_key = stock_code
            
            if (cache_key in self.price_cache and 
                cache_key in self.cache_time and
                (current_time - self.cache_time[cache_key]).seconds < 300):
                return self.price_cache[cache_key]
            
            # 确保连接
            if not self.connect():
                return 0.0
            
            # 获取实时股价
            ret, data = self.quote_ctx.get_market_snapshot([stock_code])
            if ret == ft.RET_OK and not data.empty:
                current_price = data.iloc[0]['last_price']
                
                # 更新缓存
                self.price_cache[cache_key] = current_price
                self.cache_time[cache_key] = current_time
                
                self.logger.debug(f"获取{stock_code}股价: {current_price}")
                return current_price
            else:
                self.logger.warning(f"无法获取{stock_code}股价")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"获取{stock_code}股价失败: {e}")
            return 0.0
    
    def get_multiple_stock_prices(self, stock_codes: list) -> Dict[str, float]:
        """批量获取股票价格"""
        prices = {}
        
        try:
            # 确保连接
            if not self.connect():
                return {code: 0.0 for code in stock_codes}
            
            # 批量获取股价
            ret, data = self.quote_ctx.get_market_snapshot(stock_codes)
            if ret == ft.RET_OK and not data.empty:
                current_time = datetime.now()
                
                for _, row in data.iterrows():
                    stock_code = row['code']
                    price = row['last_price']
                    
                    prices[stock_code] = price
                    
                    # 更新缓存
                    self.price_cache[stock_code] = price
                    self.cache_time[stock_code] = current_time
                
                self.logger.debug(f"批量获取{len(prices)}只股票价格")
            else:
                self.logger.warning("批量获取股价失败")
                prices = {code: 0.0 for code in stock_codes}
                
        except Exception as e:
            self.logger.error(f"批量获取股价失败: {e}")
            prices = {code: 0.0 for code in stock_codes}
        
        return prices


# 全局实例
stock_price_fetcher = StockPriceFetcher()