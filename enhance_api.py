#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API增强脚本：为期权数据添加股价、执行价格和到期日信息
"""

import re
import futu as ft
from datetime import datetime

def parse_option_code(option_code):
    """从期权代码解析执行价格和到期日"""
    try:
        # HK.ALB250905C95000 格式解析
        match = re.match(r'HK\.([A-Z]+)(\d{6})([CP])(\d+)', option_code)
        if match:
            stock_symbol, date_str, option_type, strike_str = match.groups()
            
            # 解析执行价格 (除以1000)
            strike_price = int(strike_str) / 1000
            
            # 解析到期日 (YYMMDD -> YYYY-MM-DD)
            year = 2000 + int(date_str[:2])
            month = date_str[2:4]
            day = date_str[4:6]
            expiry_date = f"{year}-{month}-{day}"
            
            # 期权类型
            option_type_str = "Call (看涨期权)" if option_type == 'C' else "Put (看跌期权)"
            
            return {
                'strike_price': strike_price,
                'expiry_date': expiry_date,
                'option_type': option_type_str
            }
    except Exception as e:
        print(f"解析期权代码失败 {option_code}: {e}")
    
    return {
        'strike_price': 0,
        'expiry_date': '',
        'option_type': '未知'
    }

def get_stock_price(stock_code):
    """获取股票当前价格"""
    try:
        quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data = quote_ctx.get_market_snapshot([stock_code])
        quote_ctx.close()
        
        if ret == ft.RET_OK and not data.empty:
            return float(data.iloc[0]['last_price'])
    except Exception as e:
        print(f"获取股价失败 {stock_code}: {e}")
    
    return 0

def enhance_option_data(option):
    """增强单个期权数据"""
    # 解析期权代码获取缺失信息
    option_code = option.get('option_code', '')
    parsed_info = parse_option_code(option_code)
    
    # 获取股价
    stock_code = option.get('stock_code', '')
    stock_price = get_stock_price(stock_code)
    
    # 合并所有信息
    enhanced_option = {
        **option,
        'strike_price': parsed_info['strike_price'],
        'expiry_date': parsed_info['expiry_date'],
        'option_type': parsed_info['option_type'],
        'stock_price': stock_price
    }
    
    return enhanced_option

if __name__ == "__main__":
    # 测试解析功能
    test_codes = ["HK.ALB250905C95000", "HK.ALB250905C92500"]
    
    for code in test_codes:
        parsed = parse_option_code(code)
        print(f"{code} -> 执行价格: {parsed['strike_price']}, 到期日: {parsed['expiry_date']}, 类型: {parsed['option_type']}")
        
        # 测试股价获取
        stock_price = get_stock_price("HK.09988")
        print(f"HK.09988 股价: {stock_price}")