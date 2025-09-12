# -*- coding: utf-8 -*-
"""
期权分析器 - 负责期权数据的分析和计算
"""

import re
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np
from scipy.stats import norm

from config import get_option_filter
from core.api_manager import OptionTrade, StockQuote


@dataclass
class OptionAnalysisResult:
    """期权分析结果"""
    option_code: str
    stock_code: str
    option_type: str  # Call/Put
    strike_price: float
    expiry_date: str
    days_to_expiry: int
    stock_price: float
    option_price: float
    volume: int
    turnover: float
    
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # 价值分析
    intrinsic_value: float = 0.0
    time_value: float = 0.0
    implied_volatility: float = 0.0
    
    # 状态分析
    moneyness: str = ""  # ITM/ATM/OTM
    risk_level: str = ""  # LOW/MEDIUM/HIGH
    importance_score: int = 0
    
    # 交易分析
    is_big_trade: bool = False
    volume_diff: int = 0
    last_volume: int = 0
    change_rate: float = 0.0


class OptionAnalyzer:
    """期权分析器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.OptionAnalyzer')
        self.volume_cache = {}  # 缓存期权交易量
        
    def analyze_option_trade(self, trade: OptionTrade, stock_quote: StockQuote = None) -> Dict[str, Any]:
        """分析期权交易"""
        try:
            # 解析期权基本信息
            option_info = self._parse_option_code(trade.option_code)
            
            # 获取股票价格
            stock_price = stock_quote.price if stock_quote else 0.0
            
            # 计算到期天数
            days_to_expiry = self._calculate_days_to_expiry(option_info['expiry_date'])
            
            # 计算Greeks和隐含波动率
            greeks = self._calculate_greeks(
                stock_price=stock_price,
                strike_price=option_info['strike_price'],
                time_to_expiry=days_to_expiry / 365.0,
                option_type=option_info['option_type'],
                option_price=trade.price
            )
            
            # 计算内在价值和时间价值
            intrinsic_value = self._calculate_intrinsic_value(
                stock_price, option_info['strike_price'], option_info['option_type']
            )
            time_value = max(0, trade.price - intrinsic_value)
            
            # 判断价值状态
            moneyness = self._determine_moneyness(
                stock_price, option_info['strike_price'], option_info['option_type']
            )
            
            # 检查是否为大单
            is_big_trade = self._is_big_trade(trade)
            
            # 计算交易量变化
            volume_diff, last_volume = self._calculate_volume_change(trade.option_code, trade.volume)
            
            # 计算重要性分数
            importance_score = self._calculate_importance_score(
                volume=trade.volume,
                turnover=trade.turnover,
                days_to_expiry=days_to_expiry,
                moneyness=moneyness,
                volume_diff=volume_diff
            )
            
            # 评估风险等级
            risk_level = self._assess_risk_level(
                days_to_expiry=days_to_expiry,
                moneyness=moneyness,
                implied_volatility=greeks.get('implied_volatility', 0),
                volume=trade.volume
            )
            
            return {
                'option_type': option_info['option_type'],
                'strike_price': option_info['strike_price'],
                'expiry_date': option_info['expiry_date'],
                'days_to_expiry': days_to_expiry,
                'stock_price': stock_price,
                'delta': greeks.get('delta', 0),
                'gamma': greeks.get('gamma', 0),
                'theta': greeks.get('theta', 0),
                'vega': greeks.get('vega', 0),
                'implied_volatility': greeks.get('implied_volatility', 0),
                'intrinsic_value': intrinsic_value,
                'time_value': time_value,
                'moneyness': moneyness,
                'is_big_trade': is_big_trade,
                'volume_diff': volume_diff,
                'last_volume': last_volume,
                'importance_score': importance_score,
                'risk_level': risk_level,
                'change_rate': 0.0  # 需要历史数据计算
            }
            
        except Exception as e:
            self.logger.error(f"分析期权交易失败: {e}")
            return {
                'option_type': 'Unknown',
                'strike_price': 0.0,
                'expiry_date': '',
                'days_to_expiry': 0,
                'is_big_trade': False,
                'importance_score': 0,
                'risk_level': 'UNKNOWN'
            }
            
    def _parse_option_code(self, option_code: str) -> Dict[str, Any]:
        """解析期权代码"""
        try:
            if not option_code.startswith('HK.'):
                return {'option_type': 'Unknown', 'strike_price': 0.0, 'expiry_date': ''}
                
            code_part = option_code[3:]  # 去掉 HK.
            
            # 解析期权类型和执行价格
            # 格式通常为: 股票代码 + 日期 + C/P + 执行价格
            match = re.search(r'(\d{6})([CP])(\d+)$', code_part)
            if match:
                date_part = match.group(1)
                option_type = 'Call' if match.group(2) == 'C' else 'Put'
                strike_part = match.group(3)
                
                # 解析日期 (YYMMDD)
                year = 2000 + int(date_part[:2])
                month = int(date_part[2:4])
                day = int(date_part[4:6])
                expiry_date = f"{year:04d}-{month:02d}-{day:02d}"
                
                # 解析执行价格 (通常需要除以1000)
                strike_price = float(strike_part) / 1000.0
                
                return {
                    'option_type': option_type,
                    'strike_price': strike_price,
                    'expiry_date': expiry_date
                }
                
        except Exception as e:
            self.logger.error(f"解析期权代码失败: {e}")
            
        return {'option_type': 'Unknown', 'strike_price': 0.0, 'expiry_date': ''}
        
    def _calculate_days_to_expiry(self, expiry_date: str) -> int:
        """计算到期天数"""
        try:
            if not expiry_date:
                return 0
                
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
            today = datetime.now()
            delta = expiry - today
            return max(0, delta.days)
            
        except Exception:
            return 0
            
    def _calculate_greeks(self, stock_price: float, strike_price: float, 
                         time_to_expiry: float, option_type: str, 
                         option_price: float) -> Dict[str, float]:
        """计算期权Greeks和隐含波动率"""
        try:
            if stock_price <= 0 or strike_price <= 0 or time_to_expiry <= 0:
                return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'implied_volatility': 0}
                
            # 使用Black-Scholes模型计算
            risk_free_rate = 0.03  # 假设无风险利率3%
            
            # 估算隐含波动率 (简化计算)
            implied_vol = self._estimate_implied_volatility(
                stock_price, strike_price, time_to_expiry, option_price, option_type, risk_free_rate
            )
            
            # 计算d1和d2
            d1 = (np.log(stock_price / strike_price) + 
                  (risk_free_rate + 0.5 * implied_vol**2) * time_to_expiry) / \
                 (implied_vol * np.sqrt(time_to_expiry))
            d2 = d1 - implied_vol * np.sqrt(time_to_expiry)
            
            # 计算Greeks
            if option_type == 'Call':
                delta = norm.cdf(d1)
                theta = (-stock_price * norm.pdf(d1) * implied_vol / (2 * np.sqrt(time_to_expiry)) -
                        risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)) / 365
            else:  # Put
                delta = norm.cdf(d1) - 1
                theta = (-stock_price * norm.pdf(d1) * implied_vol / (2 * np.sqrt(time_to_expiry)) +
                        risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)) / 365
                
            gamma = norm.pdf(d1) / (stock_price * implied_vol * np.sqrt(time_to_expiry))
            vega = stock_price * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100
            
            return {
                'delta': float(delta),
                'gamma': float(gamma),
                'theta': float(theta),
                'vega': float(vega),
                'implied_volatility': float(implied_vol * 100)  # 转换为百分比
            }
            
        except Exception as e:
            self.logger.error(f"计算Greeks失败: {e}")
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'implied_volatility': 0}
            
    def _estimate_implied_volatility(self, stock_price: float, strike_price: float,
                                   time_to_expiry: float, option_price: float,
                                   option_type: str, risk_free_rate: float) -> float:
        """估算隐含波动率 (使用牛顿法)"""
        try:
            # 初始猜测
            vol = 0.3
            
            for _ in range(10):  # 最多迭代10次
                # 计算理论价格
                d1 = (np.log(stock_price / strike_price) + 
                      (risk_free_rate + 0.5 * vol**2) * time_to_expiry) / \
                     (vol * np.sqrt(time_to_expiry))
                d2 = d1 - vol * np.sqrt(time_to_expiry)
                
                if option_type == 'Call':
                    theoretical_price = (stock_price * norm.cdf(d1) - 
                                       strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2))
                else:
                    theoretical_price = (strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - 
                                       stock_price * norm.cdf(-d1))
                
                # 计算vega
                vega = stock_price * norm.pdf(d1) * np.sqrt(time_to_expiry)
                
                if abs(vega) < 1e-6:
                    break
                    
                # 牛顿法更新
                vol = vol - (theoretical_price - option_price) / vega
                vol = max(0.01, min(5.0, vol))  # 限制在合理范围内
                
                if abs(theoretical_price - option_price) < 0.001:
                    break
                    
            return vol
            
        except Exception:
            return 0.3  # 默认30%波动率
            
    def _calculate_intrinsic_value(self, stock_price: float, strike_price: float, option_type: str) -> float:
        """计算内在价值"""
        if option_type == 'Call':
            return max(0, stock_price - strike_price)
        elif option_type == 'Put':
            return max(0, strike_price - stock_price)
        return 0.0
        
    def _determine_moneyness(self, stock_price: float, strike_price: float, option_type: str) -> str:
        """判断期权价值状态"""
        if stock_price <= 0 or strike_price <= 0:
            return "Unknown"
            
        ratio = stock_price / strike_price
        
        if option_type == 'Call':
            if ratio > 1.02:
                return "ITM"  # In The Money
            elif ratio < 0.98:
                return "OTM"  # Out of The Money
            else:
                return "ATM"  # At The Money
        elif option_type == 'Put':
            if ratio < 0.98:
                return "ITM"
            elif ratio > 1.02:
                return "OTM"
            else:
                return "ATM"
                
        return "Unknown"
        
    def _is_big_trade(self, trade: OptionTrade) -> bool:
        """判断是否为大单交易"""
        try:
            # 获取该股票的过滤条件
            option_filter = get_option_filter(trade.stock_code)
            
            return (trade.volume >= option_filter['min_volume'] and 
                   trade.turnover >= option_filter['min_turnover'])
                   
        except Exception:
            return False
            
    def _calculate_volume_change(self, option_code: str, current_volume: int) -> tuple:
        """计算交易量变化"""
        last_volume = self.volume_cache.get(option_code, 0)
        volume_diff = current_volume - last_volume
        
        # 更新缓存
        self.volume_cache[option_code] = current_volume
        
        return volume_diff, last_volume
        
    def _calculate_importance_score(self, volume: int, turnover: float, 
                                  days_to_expiry: int, moneyness: str, 
                                  volume_diff: int) -> int:
        """计算重要性分数 (0-100)"""
        score = 0
        
        # 成交量权重 (40%)
        if volume >= 100:
            score += 40
        elif volume >= 50:
            score += 30
        elif volume >= 20:
            score += 20
        elif volume >= 10:
            score += 10
            
        # 成交额权重 (30%)
        if turnover >= 1000000:  # 100万
            score += 30
        elif turnover >= 500000:  # 50万
            score += 25
        elif turnover >= 100000:  # 10万
            score += 20
        elif turnover >= 50000:   # 5万
            score += 15
        elif turnover >= 10000:   # 1万
            score += 10
            
        # 到期时间权重 (15%)
        if days_to_expiry <= 7:
            score += 15
        elif days_to_expiry <= 30:
            score += 10
        elif days_to_expiry <= 90:
            score += 5
            
        # 价值状态权重 (10%)
        if moneyness == "ATM":
            score += 10
        elif moneyness == "ITM":
            score += 8
        elif moneyness == "OTM":
            score += 5
            
        # 交易量变化权重 (5%)
        if volume_diff > 0:
            score += 5
            
        return min(100, score)
        
    def _assess_risk_level(self, days_to_expiry: int, moneyness: str, 
                          implied_volatility: float, volume: int) -> str:
        """评估风险等级"""
        risk_score = 0
        
        # 到期时间风险
        if days_to_expiry <= 7:
            risk_score += 3
        elif days_to_expiry <= 30:
            risk_score += 2
        elif days_to_expiry <= 90:
            risk_score += 1
            
        # 价值状态风险
        if moneyness == "OTM":
            risk_score += 2
        elif moneyness == "ATM":
            risk_score += 1
            
        # 隐含波动率风险
        if implied_volatility > 50:
            risk_score += 2
        elif implied_volatility > 30:
            risk_score += 1
            
        # 流动性风险
        if volume < 10:
            risk_score += 2
        elif volume < 50:
            risk_score += 1
            
        # 评级
        if risk_score >= 6:
            return "HIGH"
        elif risk_score >= 3:
            return "MEDIUM"
        else:
            return "LOW"