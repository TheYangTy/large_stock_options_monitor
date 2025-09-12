#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试期权代码解析器
"""

import sys
import os
sys.path.append('v2_system')

from v2_system.utils.option_code_parser import parse_option_code, get_option_type, get_expiry_date, get_strike_price, get_stock_code

def test_option_parser():
    """测试期权代码解析器"""
    
    # 用户提供的实际期权格式
    test_codes = [
        'HK.TCH250919C670000',  # TCH, 2025-09-19, Call, 67.0000
        'HK.BIU250919C120000',  # BIU, 2025-09-19, Call, 12.0000  
        'HK.JDC250929P122500',  # JDC, 2025-09-29, Put, 12.2500
    ]
    
    print("=== V2系统期权代码解析测试 ===\n")
    
    for code in test_codes:
        print(f"测试期权代码: {code}")
        
        # 完整解析
        result = parse_option_code(code)
        print(f"完整解析结果: {result}")
        
        # 单独获取各项信息
        print(f"股票代码: {get_stock_code(code)}")
        print(f"期权类型: {get_option_type(code)}")
        print(f"到期日: {get_expiry_date(code)}")
        print(f"行权价格: {get_strike_price(code)}")
        print(f"解析成功: {result.get('is_valid', False)}")
        print("-" * 50)

if __name__ == "__main__":
    test_option_parser()