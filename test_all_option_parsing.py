#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试所有期权代码解析修复
"""

import sys
import os

def test_v1_parsing():
    """测试V1系统的期权解析"""
    print("=== 测试V1系统期权解析 ===")
    
    from utils.option_code_parser import get_option_type, get_stock_code
    
    test_codes = [
        'HK.TCH250919C670000',  # TCH, Call
        'HK.BIU250919C120000',  # BIU, Call  
        'HK.JDC250929P122500',  # JDC, Put
    ]
    
    for code in test_codes:
        option_type = get_option_type(code)
        stock_code = get_stock_code(code)
        print(f"  {code} -> 类型: {option_type}, 股票: {stock_code}")
    
    print()

def test_wework_notifier():
    """测试企微通知器的期权解析"""
    print("=== 测试企微通知器期权解析 ===")
    
    from utils.wework_notifier import WeWorkNotifier
    
    notifier = WeWorkNotifier("dummy_webhook")
    
    test_codes = [
        'HK.TCH250919C670000',
        'HK.JDC250929P122500',
    ]
    
    for code in test_codes:
        option_type = notifier._parse_option_type(code)
        print(f"  {code} -> 类型: {option_type}")
    
    print()

def test_enhanced_processor():
    """测试增强期权处理器"""
    print("=== 测试增强期权处理器 ===")
    
    try:
        from utils.enhanced_option_processor import EnhancedOptionProcessor
        
        processor = EnhancedOptionProcessor()
        
        test_codes = [
            'HK.TCH250919C670000',
            'HK.JDC250929P122500',
        ]
        
        for code in test_codes:
            # 调用正确的方法名
            option_type = processor._parse_option_type(code)
            print(f"  {code} -> 类型显示: {option_type}")
    except Exception as e:
        print(f"  增强处理器测试失败: {e}")
    
    print()

def test_direction_analyzer():
    """测试方向分析器"""
    print("=== 测试方向分析器 ===")
    
    try:
        from utils.direction_analyzer import DirectionAnalyzer
        
        analyzer = DirectionAnalyzer()
        
        test_data = [
            {'option_code': 'HK.TCH250919C670000', 'volume': 1000, 'turnover': 50000},
            {'option_code': 'HK.JDC250929P122500', 'volume': 500, 'turnover': 30000},
        ]
        
        for data in test_data:
            direction = analyzer.analyze_direction(data)
            print(f"  {data['option_code']} -> 方向: {direction}")
    except Exception as e:
        print(f"  方向分析器测试失败: {e}")
    
    print()

def test_v2_parsing():
    """测试V2系统的期权解析"""
    print("=== 测试V2系统期权解析 ===")
    
    try:
        sys.path.append('v2_system')
        from v2_system.utils.option_code_parser import get_option_type, get_stock_code
        
        test_codes = [
            'HK.TCH250919C670000',
            'HK.BIU250919C120000',  
            'HK.JDC250929P122500',
        ]
        
        for code in test_codes:
            option_type = get_option_type(code)
            stock_code = get_stock_code(code)
            print(f"  {code} -> 类型: {option_type}, 股票: {stock_code}")
    except Exception as e:
        print(f"  V2系统测试失败: {e}")
    
    print()

def main():
    """主测试函数"""
    print("🧪 期权代码解析修复验证测试\n")
    
    test_v1_parsing()
    test_wework_notifier()
    test_enhanced_processor()
    test_direction_analyzer()
    test_v2_parsing()
    
    print("✅ 所有测试完成")

if __name__ == "__main__":
    main()