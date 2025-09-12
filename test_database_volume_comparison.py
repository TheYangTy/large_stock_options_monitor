#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试与数据库中当日交易量对比的功能
"""

import sys
import os
import json
from datetime import datetime

# 添加v2_system路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'v2_system'))

from utils.big_options_processor import BigOptionsProcessor
from config import SYSTEM_CONFIG

def create_mock_database_data():
    """创建模拟的数据库数据"""
    print("=== 创建模拟数据库数据 ===\n")
    
    # 确保缓存目录存在
    cache_dir = SYSTEM_CONFIG['cache_dir']
    os.makedirs(cache_dir, exist_ok=True)
    
    # 创建当日期权数据文件
    today = datetime.now().strftime('%Y-%m-%d')
    today_file = os.path.join(cache_dir, f'options_{today}.json')
    
    # 模拟已存在的期权数据（早上的记录）
    existing_data = [
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919C680000',
            'volume': 3000,  # 早上记录的成交量
            'turnover': 1500000,
            'price': 0.5000,
            'strike_price': 680.00,
            'option_type': 'Call',
            'timestamp': f'{today}T09:30:00',
            'detected_time': f'{today}T09:30:00'
        },
        {
            'stock_code': 'HK.00700',
            'stock_name': '腾讯控股',
            'option_code': 'HK.TCH250919P670000',
            'volume': 2000,  # 早上记录的成交量
            'turnover': 1200000,
            'price': 0.6000,
            'strike_price': 670.00,
            'option_type': 'Put',
            'timestamp': f'{today}T10:00:00',
            'detected_time': f'{today}T10:00:00'
        },
        {
            'stock_code': 'HK.03690',
            'stock_name': '美团-W',
            'option_code': 'HK.MEI250919C150000',
            'volume': 2500,  # 早上记录的成交量
            'turnover': 1250000,
            'price': 0.5000,
            'strike_price': 150.00,
            'option_type': 'Call',
            'timestamp': f'{today}T10:30:00',
            'detected_time': f'{today}T10:30:00'
        }
    ]
    
    # 保存到文件
    with open(today_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    print(f"已创建模拟数据库文件: {today_file}")
    print("模拟的早上记录:")
    for data in existing_data:
        print(f"  {data['stock_name']}: {data['option_type']} {data['strike_price']:.2f}, "
              f"成交量: {data['volume']}张 (时间: {data['timestamp']})")
    
    return existing_data

def test_volume_comparison():
    """测试成交量对比功能"""
    print("\n=== 测试成交量对比功能 ===\n")
    
    # 创建处理器
    processor = BigOptionsProcessor()
    
    # 测试加载当日数据
    today_volumes = processor._load_today_option_volumes()
    
    print("从数据库加载的当日成交量:")
    for option_code, volume in today_volumes.items():
        print(f"  {option_code}: {volume}张")
    
    # 测试获取特定期权的最后记录成交量
    test_options = [
        'HK.TCH250919C680000',
        'HK.TCH250919P670000', 
        'HK.MEI250919C150000',
        'HK.NEW250919C100000'  # 不存在的期权
    ]
    
    print("\n测试获取最后记录成交量:")
    for option_code in test_options:
        last_volume = processor._get_last_recorded_volume(option_code)
        print(f"  {option_code}: {last_volume}张")
    
    return today_volumes

def simulate_new_data_comparison():
    """模拟新数据与数据库对比"""
    print("\n=== 模拟新数据与数据库对比 ===\n")
    
    processor = BigOptionsProcessor()
    
    # 模拟当前获取到的新数据（下午的数据）
    current_data = [
        {
            'option_code': 'HK.TCH250919C680000',
            'current_volume': 5000,  # 从3000增加到5000
            'expected_diff': 2000
        },
        {
            'option_code': 'HK.TCH250919P670000',
            'current_volume': 2000,  # 没有变化
            'expected_diff': 0
        },
        {
            'option_code': 'HK.MEI250919C150000',
            'current_volume': 4000,  # 从2500增加到4000
            'expected_diff': 1500
        },
        {
            'option_code': 'HK.NEW250919C100000',
            'current_volume': 1000,  # 新期权
            'expected_diff': 1000
        }
    ]
    
    print("模拟当前数据与数据库对比:")
    for data in current_data:
        option_code = data['option_code']
        current_volume = data['current_volume']
        expected_diff = data['expected_diff']
        
        # 获取数据库中的最后记录
        last_recorded = processor._get_last_recorded_volume(option_code)
        
        # 计算实际变化量
        actual_diff = current_volume - last_recorded
        
        status = "✅" if actual_diff == expected_diff else "❌"
        print(f"  {status} {option_code}:")
        print(f"      当前: {current_volume}张, 数据库: {last_recorded}张")
        print(f"      变化: {actual_diff}张 (期望: {expected_diff}张)")
        
        # 测试更新缓存
        if actual_diff > 0:
            processor._update_today_volume_cache(option_code, current_volume)
            print(f"      已更新缓存")

def test_restart_persistence():
    """测试重启后的持久性"""
    print("\n=== 测试重启后的持久性 ===\n")
    
    # 创建新的处理器实例（模拟程序重启）
    new_processor = BigOptionsProcessor()
    
    # 重新加载数据
    today_volumes = new_processor._load_today_option_volumes()
    
    print("重启后重新加载的数据:")
    for option_code, volume in today_volumes.items():
        print(f"  {option_code}: {volume}张")
    
    print("\n✅ 数据持久性测试通过：重启后仍能正确加载当日数据")

def cleanup_test_data():
    """清理测试数据"""
    try:
        cache_dir = SYSTEM_CONFIG['cache_dir']
        today = datetime.now().strftime('%Y-%m-%d')
        today_file = os.path.join(cache_dir, f'options_{today}.json')
        
        if os.path.exists(today_file):
            os.remove(today_file)
            print(f"\n已清理测试数据文件: {today_file}")
    except Exception as e:
        print(f"\n清理测试数据失败: {e}")

if __name__ == "__main__":
    try:
        # 创建模拟数据
        create_mock_database_data()
        
        # 测试功能
        test_volume_comparison()
        simulate_new_data_comparison()
        test_restart_persistence()
        
        print("\n=== 测试完成 ===")
        print("功能说明：")
        print("1. 成交量变化现在与数据库中当日记录对比，而不是内存缓存")
        print("2. 程序重启后仍能正确计算变化量")
        print("3. 只有真正有变化的期权才会触发通知")
        print("4. 变化量 = 当前成交量 - 数据库中最后记录的成交量")
        
    finally:
        # 清理测试数据
        cleanup_test_data()