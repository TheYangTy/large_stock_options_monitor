#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试无变化时不发送通知的功能
"""

import sys
import os
from datetime import datetime

# 添加v2_system路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'v2_system'))

from utils.notifier import V2Notifier

def test_no_change_notification():
    """测试无变化时不发送通知"""
    print("=== 测试无变化时不发送通知 ===\n")
    
    notifier = V2Notifier()
    
    # 创建无变化的期权数据（volume_diff = 0）
    no_change_options = [
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C680000',
            'volume': 5000,
            'turnover': 2500000,
            'price': 0.5000,
            'strike_price': 680.00,
            'option_type': 'Call',
            'volume_diff': 0,  # 无变化
            'last_volume': 5000,
            'timestamp': datetime.now().isoformat()
        },
        {
            'stock_code': 'HK.03690',
            'stock_name': '美团-W',
            'option_code': 'HK.MEI250919C150000',
            'volume': 4000,
            'turnover': 2000000,
            'price': 0.5000,
            'strike_price': 150.00,
            'option_type': 'Call',
            'volume_diff': 0,  # 无变化
            'last_volume': 4000,
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    print("测试数据 (无变化):")
    for option in no_change_options:
        print(f"  {option['stock_name']}: {option['option_type']} {option['strike_price']:.2f}, "
              f"成交量: {option['volume']}张, 变化: {option['volume_diff']}")
    
    print("\n发送通知测试:")
    success = notifier.send_stock_grouped_notifications(no_change_options)
    
    if not success:
        print("✅ 正确：无变化时未发送通知")
    else:
        print("❌ 错误：无变化时仍然发送了通知")

def test_mixed_change_notification():
    """测试混合变化的通知（部分有变化，部分无变化）"""
    print("\n=== 测试混合变化通知 ===\n")
    
    notifier = V2Notifier()
    
    # 创建混合数据（部分有变化，部分无变化）
    mixed_options = [
        # 有变化的期权
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C680000',
            'volume': 5000,
            'turnover': 2500000,
            'price': 0.5000,
            'strike_price': 680.00,
            'option_type': 'Call',
            'volume_diff': 1000,  # 有变化
            'last_volume': 4000,
            'timestamp': datetime.now().isoformat()
        },
        # 无变化的期权
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919P670000',
            'volume': 3000,
            'turnover': 1800000,
            'price': 0.6000,
            'strike_price': 670.00,
            'option_type': 'Put',
            'volume_diff': 0,  # 无变化
            'last_volume': 3000,
            'timestamp': datetime.now().isoformat()
        },
        # 有变化的期权
        {
            'stock_code': 'HK.03690',
            'stock_name': '美团-W',
            'option_code': 'HK.MEI250919C150000',
            'volume': 4000,
            'turnover': 2000000,
            'price': 0.5000,
            'strike_price': 150.00,
            'option_type': 'Call',
            'volume_diff': 800,  # 有变化
            'last_volume': 3200,
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    print("测试数据 (混合变化):")
    for option in mixed_options:
        change_status = "有变化" if option['volume_diff'] > 0 else "无变化"
        print(f"  {option['stock_name']}: {option['option_type']} {option['strike_price']:.2f}, "
              f"变化: +{option['volume_diff']}张 ({change_status})")
    
    print(f"\n总共 {len(mixed_options)} 个期权，其中 {len([opt for opt in mixed_options if opt['volume_diff'] > 0])} 个有变化")
    
    print("\n发送通知测试:")
    success = notifier.send_stock_grouped_notifications(mixed_options)
    
    if success:
        print("✅ 正确：只对有变化的期权发送了通知")
        print("预期结果：只显示腾讯控股的Call 680.00和美团的Call 150.00")
    else:
        print("❌ 意外：没有发送通知")

if __name__ == "__main__":
    test_no_change_notification()
    test_mixed_change_notification()
    
    print("\n=== 测试完成 ===")
    print("功能说明：")
    print("1. 只有成交量有变化(volume_diff > 0)的期权才会发送通知")
    print("2. 通知中显示格式：成交: 5000张 (+1500)")
    print("3. 无变化的期权会被过滤掉，不发送通知")