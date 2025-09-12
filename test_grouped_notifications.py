#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试按股票分组的期权通知
"""

import sys
import os
from datetime import datetime

# 添加v2_system路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'v2_system'))

from utils.notifier import V2Notifier

def create_test_options():
    """创建测试用的大单期权数据"""
    test_options = [
        # 腾讯控股 - 3个期权
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C680000',
            'volume': 5000,
            'turnover': 2500000,  # 250万
            'price': 0.5000,
            'strike_price': 680.00,
            'option_type': 'Call',
            'direction': 'BUY',
            'volume_diff': 1500,  # 新增1500张
            'last_volume': 3500,  # 上次3500张
            'timestamp': datetime.now().isoformat()
        },
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919P670000',
            'volume': 3000,
            'turnover': 1800000,  # 180万
            'price': 0.6000,
            'strike_price': 670.00,
            'option_type': 'Put',
            'direction': 'SELL',
            'volume_diff': 800,   # 新增800张
            'last_volume': 2200,  # 上次2200张
            'timestamp': datetime.now().isoformat()
        },
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C690000',
            'volume': 2000,
            'turnover': 1200000,  # 120万
            'price': 0.6000,
            'strike_price': 690.00,
            'option_type': 'Call',
            'direction': 'BUY',
            'volume_diff': 500,   # 新增500张
            'last_volume': 1500,  # 上次1500张
            'timestamp': datetime.now().isoformat()
        },
        # 美团 - 2个期权
        {
            'stock_code': 'HK.03690',
            'stock_name': '美团-W',
            'option_code': 'HK.MEI250919C150000',
            'volume': 4000,
            'turnover': 2000000,  # 200万
            'price': 0.5000,
            'strike_price': 150.00,
            'option_type': 'Call',
            'direction': 'BUY',
            'volume_diff': 1200,  # 新增1200张
            'last_volume': 2800,  # 上次2800张
            'timestamp': datetime.now().isoformat()
        },
        {
            'stock_code': 'HK.03690',
            'stock_name': '美团-W',
            'option_code': 'HK.MEI250919P140000',
            'volume': 2500,
            'turnover': 1500000,  # 150万
            'price': 0.6000,
            'strike_price': 140.00,
            'option_type': 'Put',
            'direction': 'NEUTRAL',
            'volume_diff': 600,   # 新增600张
            'last_volume': 1900,  # 上次1900张
            'timestamp': datetime.now().isoformat()
        },
        # 小米 - 1个期权
        {
            'stock_code': 'HK.01810',
            'stock_name': '小米集团-W',
            'option_code': 'HK.BIU250919C120000',
            'volume': 8000,
            'turnover': 800000,  # 80万
            'price': 0.1000,
            'strike_price': 12.00,
            'option_type': 'Call',
            'direction': 'BUY',
            'volume_diff': 2000,  # 新增2000张
            'last_volume': 6000,  # 上次6000张
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    return test_options

def test_grouped_notifications():
    """测试按股票分组的通知"""
    print("=== 测试V2系统按股票分组的期权通知 ===\n")
    
    # 创建通知器
    notifier = V2Notifier()
    
    # 创建测试数据
    test_options = create_test_options()
    
    print("测试数据:")
    for option in test_options:
        print(f"  {option['stock_name']}: {option['option_type']} {option['strike_price']:.2f}, "
              f"成交额: {option['turnover']/10000:.1f}万港币")
    
    print(f"\n总共 {len(test_options)} 笔大单期权，涉及 3 只股票")
    
    # 测试分组通知
    print("\n=== 发送分组通知 ===")
    success = notifier.send_stock_grouped_notifications(test_options)
    
    if success:
        print("✅ 分组通知发送成功")
    else:
        print("❌ 分组通知发送失败")
    
    print("\n预期结果:")
    print("- 腾讯控股: 显示前3个期权 (250万, 180万, 120万)")
    print("- 美团-W: 显示前2个期权 (200万, 150万)")
    print("- 小米集团-W: 显示1个期权 (80万)")

def test_single_stock_notification():
    """测试单个股票的通知"""
    print("\n=== 测试单个股票通知 ===\n")
    
    notifier = V2Notifier()
    
    # 创建腾讯的期权数据
    tencent_options = [
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C680000',
            'volume': 5000,
            'turnover': 2500000,
            'price': 0.5000,
            'strike_price': 680.00,
            'option_type': 'Call',
            'direction': 'BUY',
            'timestamp': datetime.now().isoformat()
        },
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919P670000',
            'volume': 3000,
            'turnover': 1800000,
            'price': 0.6000,
            'strike_price': 670.00,
            'option_type': 'Put',
            'direction': 'SELL',
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    success = notifier._send_stock_group_notification('HK.00700', '腾讯控股', tencent_options)
    
    if success:
        print("✅ 单个股票通知发送成功")
    else:
        print("❌ 单个股票通知发送失败")

if __name__ == "__main__":
    test_grouped_notifications()
    test_single_stock_notification()
    
    print("\n=== 测试完成 ===")
    print("注意: 实际的企微和Mac通知可能不会发送，但控制台输出应该显示正确的分组格式")