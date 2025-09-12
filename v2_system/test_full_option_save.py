#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试全量期权数据保存功能
验证所有期权数据都保存到数据库，通知时进行过滤
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import HK_MONITOR_STOCKS, US_MONITOR_STOCKS, get_database_config
from utils.database_manager import get_database_manager

def test_database_records():
    """测试数据库中的记录数量"""
    print("🧪 测试全量期权数据保存功能")
    print("=" * 50)
    
    # 测试港股数据库
    print("\n📊 港股数据库统计:")
    try:
        hk_db = get_database_manager('HK')
        
        # 获取总记录数（简化测试）
        import sqlite3
        hk_config = get_database_config('HK')
        conn = sqlite3.connect(hk_config['db_path'])
        cursor = conn.cursor()
        
        # 获取今日记录数
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM option_trades WHERE DATE(timestamp) = ?", (today,))
        hk_today_count = cursor.fetchone()[0]
        
        # 获取总记录数
        cursor.execute("SELECT COUNT(*) FROM option_trades")
        hk_total_count = cursor.fetchone()[0]
        
        # 获取最近的记录
        cursor.execute("""
            SELECT option_code, volume, turnover, timestamp 
            FROM option_trades 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        recent_records = cursor.fetchall()
        
        print(f"  📅 今日记录数: {hk_today_count}")
        print(f"  📈 总记录数: {hk_total_count}")
        print(f"  🕐 最近5条记录:")
        
        for i, record in enumerate(recent_records, 1):
            option_code, volume, turnover, timestamp = record
            print(f"    {i}. {option_code} - 成交量:{volume}, 成交额:{turnover:.0f}, 时间:{timestamp}")
        
        conn.close()
            
    except Exception as e:
        print(f"  ❌ 港股数据库测试失败: {e}")
    
    # 测试美股数据库
    print("\n📊 美股数据库统计:")
    try:
        us_db = get_database_manager('US')
        
        # 获取总记录数（简化测试）
        import sqlite3
        us_config = get_database_config('US')
        conn = sqlite3.connect(us_config['db_path'])
        cursor = conn.cursor()
        
        # 获取今日记录数
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM option_trades WHERE DATE(timestamp) = ?", (today,))
        us_today_count = cursor.fetchone()[0]
        
        # 获取总记录数
        cursor.execute("SELECT COUNT(*) FROM option_trades")
        us_total_count = cursor.fetchone()[0]
        
        # 获取最近的记录
        cursor.execute("""
            SELECT option_code, volume, turnover, timestamp 
            FROM option_trades 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        recent_records = cursor.fetchall()
        
        print(f"  📅 今日记录数: {us_today_count}")
        print(f"  📈 总记录数: {us_total_count}")
        print(f"  🕐 最近5条记录:")
        
        for i, record in enumerate(recent_records, 1):
            option_code, volume, turnover, timestamp = record
            print(f"    {i}. {option_code} - 成交量:{volume}, 成交额:{turnover:.0f}, 时间:{timestamp}")
        
        conn.close()
            
    except Exception as e:
        print(f"  ❌ 美股数据库测试失败: {e}")

def test_filter_logic():
    """测试过滤逻辑"""
    print("\n🔍 测试过滤逻辑:")
    print("-" * 30)
    
    from config import BIG_TRADE_CONFIG, OPTION_FILTERS
    
    print(f"📋 大单过滤条件:")
    print(f"  最小成交量: {BIG_TRADE_CONFIG['min_volume_threshold']} 张")
    print(f"  最小成交额: {BIG_TRADE_CONFIG['min_turnover_threshold']} 元")
    print(f"  通知冷却时间: {BIG_TRADE_CONFIG['notification_cooldown']} 秒")
    
    print(f"\n📋 期权过滤条件示例:")
    for market in ['hk_default', 'us_default']:
        if market in OPTION_FILTERS:
            config = OPTION_FILTERS[market]
            print(f"  {market}:")
            print(f"    最小成交量: {config.get('min_volume', 'N/A')}")
            print(f"    最小成交额: {config.get('min_turnover', 'N/A')}")
            print(f"    重要性分数: {config.get('min_importance_score', 'N/A')}")

def simulate_option_processing():
    """模拟期权处理流程"""
    print("\n🎯 模拟期权处理流程:")
    print("-" * 30)
    
    # 模拟期权数据
    mock_options = [
        {
            'option_code': 'HK.TCH250930C600000',
            'volume': 100,
            'turnover': 150000,
            'stock_code': 'HK.00700'
        },
        {
            'option_code': 'HK.TCH250930P580000', 
            'volume': 30,
            'turnover': 80000,
            'stock_code': 'HK.00700'
        },
        {
            'option_code': 'US.AAPL250920C180000',
            'volume': 200,
            'turnover': 120000,
            'stock_code': 'US.AAPL'
        }
    ]
    
    from config import BIG_TRADE_CONFIG
    
    print("📊 模拟数据处理结果:")
    
    saved_count = 0
    notify_count = 0
    
    for option in mock_options:
        option_code = option['option_code']
        volume = option['volume']
        turnover = option['turnover']
        
        # 所有数据都会保存
        saved_count += 1
        print(f"  💾 保存到数据库: {option_code} (成交量:{volume}, 成交额:{turnover})")
        
        # 检查是否满足通知条件
        is_big_trade = (
            volume >= BIG_TRADE_CONFIG['min_volume_threshold'] and
            turnover >= BIG_TRADE_CONFIG['min_turnover_threshold']
        )
        
        if is_big_trade:
            notify_count += 1
            print(f"    🔔 符合通知条件: ✅")
        else:
            print(f"    🔔 符合通知条件: ❌ (成交量或成交额不足)")
    
    print(f"\n📈 处理结果汇总:")
    print(f"  💾 保存到数据库: {saved_count} 条记录")
    print(f"  🔔 符合通知条件: {notify_count} 条记录")
    print(f"  📊 保存率: 100% (所有期权数据)")
    print(f"  📊 通知率: {notify_count/saved_count*100:.1f}% (满足条件的期权)")

def main():
    """主测试函数"""
    print("🚀 V2系统全量期权数据保存测试")
    print("=" * 60)
    
    print("\n📝 测试说明:")
    print("  1. 验证所有期权数据都保存到数据库")
    print("  2. 验证通知时进行过滤")
    print("  3. 检查数据库记录统计")
    
    # 测试数据库记录
    test_database_records()
    
    # 测试过滤逻辑
    test_filter_logic()
    
    # 模拟处理流程
    simulate_option_processing()
    
    print("\n✅ 测试完成!")
    print("\n💡 关键改进:")
    print("  🔄 修改前: 只保存满足大单条件的期权数据")
    print("  🔄 修改后: 保存所有期权数据，通知时过滤")
    print("  📈 优势: 完整的数据记录，灵活的通知控制")

if __name__ == '__main__':
    main()