# -*- coding: utf-8 -*-
"""
V1系统期权代码解析器 - 统一解析期权到期日、类型和行权价格
"""

import re
from datetime import datetime, date
from typing import Dict, Optional, Tuple, Union, Any
import logging

logger = logging.getLogger(__name__)


class OptionCodeParser:
    """期权代码解析器"""
    
    def __init__(self):
        # 港股期权代码正则模式
        # 实际格式: HK.TCH250919C670000 (股票简称TCH，2025年09月19日，Call，行权价67.0000)
        # 实际格式: HK.BIU250919C120000 (股票简称BIU，2025年09月19日，Call，行权价12.0000)
        # 实际格式: HK.JDC250929P122500 (股票简称JDC，2025年09月29日，Put，行权价12.2500)
        self.hk_option_patterns = [
            # 主要格式: HK.{股票简称}{YYMMDD}{C/P}{价格}
            r'HK\.([A-Z]{2,5})(\d{2})(\d{2})(\d{2})([CP])(\d+)',
            # 备用格式: 可能的其他变体
            r'HK\.([A-Z0-9]{2,5})(\d{6})([CP])(\d+)',
        ]
    
    def parse_option_code(self, option_code: str) -> Dict[str, Any]:
        """
        解析期权代码，返回包含所有信息的字典
        
        Args:
            option_code: 期权代码，如 'HK.TCH250919C670000'
            
        Returns:
            Dict包含:
            - stock_code: 股票代码 (如 'HK.TCH')
            - option_type: 期权类型 ('Call' 或 'Put')
            - expiry_date: 到期日 (YYYY-MM-DD格式)
            - strike_price: 行权价格 (浮点数)
            - is_valid: 是否解析成功
            - raw_code: 原始代码
        """
        result = {
            'stock_code': None,
            'option_type': None,
            'expiry_date': None,
            'strike_price': None,
            'is_valid': False,
            'raw_code': option_code
        }
        
        try:
            if not option_code or not isinstance(option_code, str):
                return result
            
            option_code = option_code.strip().upper()
            
            # 尝试港股期权格式
            if option_code.startswith('HK.'):
                parsed = self._parse_hk_option(option_code)
                if parsed['is_valid']:
                    return parsed
            
            logger.debug(f"V1无法解析期权代码: {option_code}")
            return result
            
        except Exception as e:
            logger.error(f"V1解析期权代码异常: {option_code}, 错误: {e}")
            return result
    
    def _parse_hk_option(self, option_code: str) -> Dict[str, Any]:
        """解析港股期权代码"""
        result = {
            'stock_code': None,
            'option_type': None,
            'expiry_date': None,
            'strike_price': None,
            'is_valid': False,
            'raw_code': option_code
        }
        
        # 主要模式: HK.{股票简称}{YYMMDD}{C/P}{价格}
        # 例如: HK.TCH250919C670000
        pattern1 = r'HK\.([A-Z]{2,5})(\d{2})(\d{2})(\d{2})([CP])(\d+)'
        match = re.match(pattern1, option_code)
        if match:
            stock_symbol = match.group(1)  # 股票简称，如TCH, BIU, JDC
            year = match.group(2)          # 年份，如25
            month = match.group(3)         # 月份，如09
            day = match.group(4)           # 日期，如19
            option_type_char = match.group(5)  # C或P
            strike_raw = match.group(6)    # 行权价格，如670000
            
            # 构建股票代码 (保持简称格式)
            result['stock_code'] = f'HK.{stock_symbol}'
            
            # 解析期权类型
            result['option_type'] = 'Call' if option_type_char == 'C' else 'Put'
            
            # 解析到期日
            try:
                # 年份处理：25 -> 2025
                full_year = 2000 + int(year)
                if full_year < 2020:  # 如果小于2020，认为是下个世纪
                    full_year += 100
                
                expiry_date = date(full_year, int(month), int(day))
                result['expiry_date'] = expiry_date.strftime('%Y-%m-%d')
            except ValueError as e:
                logger.error(f"V1解析到期日失败: {year}-{month}-{day}, 错误: {e}")
                return result
            
            # 解析行权价格
            try:
                # 根据实际格式，价格需要除以10000
                # 670000 -> 67.0000, 120000 -> 12.0000, 122500 -> 12.2500
                strike_price = float(strike_raw) / 10000.0
                result['strike_price'] = strike_price
            except ValueError:
                logger.error(f"V1解析行权价格失败: {strike_raw}")
            
            result['is_valid'] = True
            return result
        
        return result
    
    def get_option_type(self, option_code: str) -> str:
        """获取期权类型"""
        parsed = self.parse_option_code(option_code)
        return parsed.get('option_type', '未知')
    
    def get_expiry_date(self, option_code: str) -> Optional[str]:
        """获取到期日"""
        parsed = self.parse_option_code(option_code)
        return parsed.get('expiry_date')
    
    def get_strike_price(self, option_code: str) -> Optional[float]:
        """获取行权价格"""
        parsed = self.parse_option_code(option_code)
        return parsed.get('strike_price')
    
    def get_stock_code(self, option_code: str) -> Optional[str]:
        """获取标的股票代码"""
        parsed = self.parse_option_code(option_code)
        return parsed.get('stock_code')


# 全局解析器实例
option_parser = OptionCodeParser()


def parse_option_code(option_code: str) -> Dict[str, Any]:
    """便捷函数：解析期权代码"""
    return option_parser.parse_option_code(option_code)


def get_option_type(option_code: str) -> str:
    """便捷函数：获取期权类型"""
    return option_parser.get_option_type(option_code)


def get_expiry_date(option_code: str) -> Optional[str]:
    """便捷函数：获取到期日"""
    return option_parser.get_expiry_date(option_code)


def get_strike_price(option_code: str) -> Optional[float]:
    """便捷函数：获取行权价格"""
    return option_parser.get_strike_price(option_code)


def get_stock_code(option_code: str) -> Optional[str]:
    """便捷函数：获取标的股票代码"""
    return option_parser.get_stock_code(option_code)