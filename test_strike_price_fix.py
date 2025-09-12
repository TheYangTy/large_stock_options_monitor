#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试执行价格修复
"""

import sys
import os

# 添加v2_system路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'v2_system'))

from utils.option_code_parser import parse_option_code, get_strike_price
from utils.big_options_processor import BigOptionsProcessor

def test_strike_price_parsing():
    """测试执行价格解析"""
    print("=== 测试执行价格解析修复 ===\n")
    
    # 测试用例
    test_cases = [
        ("HK.TCH250919C680000", 680.00, "腾讯控股 Call 680"),
        ("HK.TCH250919P680000", 680.00, "腾讯控股 Put 680"),
        ("HK.TCH250919C670000", 670.00, "腾讯控股 Call 670"),
        ("HK.BIU250919C120000", 12.00, "小米 Call 12"),
        ("HK.JDC250929P122500", 122.50, "京东 Put 122.5"),
        ("HK.MEI250919C150000", 150.00, "美团 Call 150"),
    ]
    
    print("1. 测试期权代码解析器:")
    for option_code, expected_price, description in test_cases:
        try:
            # 使用解析器
            parsed = parse_option_code(option_code)
            actual_price = parsed.get('strike_price', 0)
            
            status = "✅" if abs(actual_price - expected_price) < 0.01 else "❌"
            print(f"   {status} {option_code} -> {actual_price:.2f} (期望: {expected_price:.2f}) - {description}")
            
            if parsed.get('is_valid'):
                print(f"      类型: {parsed.get('option_type')}, 到期: {parsed.get('expiry_date')}")
            else:
                print(f"      解析失败")
                
        except Exception as e:
            print(f"   ❌ {option_code} -> 异常: {e}")
    
    print("\n2. 测试BigOptionsProcessor:")
    processor = BigOptionsProcessor()
    
    for option_code, expected_price, description in test_cases:
        try:
            actual_price = processor._parse_strike_from_code(option_code)
            status = "✅" if abs(actual_price - expected_price) < 0.01 else "❌"
            print(f"   {status} {option_code} -> {actual_price:.2f} (期望: {expected_price:.2f}) - {description}")
        except Exception as e:
            print(f"   ❌ {option_code} -> 异常: {e}")
    
    print("\n3. 测试便捷函数:")
    for option_code, expected_price, description in test_cases:
        try:
            actual_price = get_strike_price(option_code)
            status = "✅" if actual_price and abs(actual_price - expected_price) < 0.01 else "❌"
            actual_display = f"{actual_price:.2f}" if actual_price else "0.00"
            print(f"   {status} {option_code} -> {actual_display} (期望: {expected_price:.2f}) - {description}")
        except Exception as e:
            print(f"   ❌ {option_code} -> 异常: {e}")

def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===\n")
    
    edge_cases = [
        ("HK.TCH250919C1000000", 1000.00, "腾讯 1000港币"),  # 7位数
        ("HK.TCH250919C50000", 50.00, "腾讯 50港币"),      # 5位数
        ("HK.BIU250919C80000", 8.00, "小米 8港币"),        # 低价股6位数
        ("HK.ABC250919C12345", 123.45, "测试股 123.45"),   # 5位数带小数
    ]
    
    for option_code, expected_price, description in edge_cases:
        try:
            parsed = parse_option_code(option_code)
            actual_price = parsed.get('strike_price', 0)
            
            status = "✅" if abs(actual_price - expected_price) < 0.01 else "❌"
            print(f"   {status} {option_code} -> {actual_price:.2f} (期望: {expected_price:.2f}) - {description}")
            
        except Exception as e:
            print(f"   ❌ {option_code} -> 异常: {e}")

if __name__ == "__main__":
    test_strike_price_parsing()
    test_edge_cases()
    
    print("\n=== 测试完成 ===")
    print("如果看到 ✅，说明修复成功")
    print("如果看到 ❌，说明还需要进一步调整")