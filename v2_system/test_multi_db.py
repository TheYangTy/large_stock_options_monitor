#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试多市场数据库功能
"""

import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils.database_manager import get_database_manager
from config import get_database_config

def test_multi_market_db():
    """测试多市场数据库功能"""
    print("🧪 测试多市场数据库功能")
    print("=" * 50)
    
    # 测试港股数据库
    print("\n🇭🇰 测试港股数据库:")
    hk_db = get_database_manager('HK')
    hk_config = get_database_config('HK')
    print(f"  数据库路径: {hk_config['db_path']}")
    print(f"  数据库管理器: {hk_db}")
    
    hk_stats = hk_db.get_database_stats()
    print(f"  总记录数: {hk_stats.get('total_records', 0)}")
    print(f"  今日记录数: {hk_stats.get('today_records', 0)}")
    print(f"  股票数量: {hk_stats.get('stock_records', 0)}")
    
    # 测试美股数据库
    print("\n🇺🇸 测试美股数据库:")
    us_db = get_database_manager('US')
    us_config = get_database_config('US')
    print(f"  数据库路径: {us_config['db_path']}")
    print(f"  数据库管理器: {us_db}")
    
    us_stats = us_db.get_database_stats()
    print(f"  总记录数: {us_stats.get('total_records', 0)}")
    print(f"  今日记录数: {us_stats.get('today_records', 0)}")
    print(f"  股票数量: {us_stats.get('stock_records', 0)}")
    
    # 验证是否为不同的数据库实例
    print(f"\n🔍 验证数据库分离:")
    print(f"  港股数据库路径: {hk_db.db_path}")
    print(f"  美股数据库路径: {us_db.db_path}")
    print(f"  数据库是否分离: {'✅ 是' if hk_db.db_path != us_db.db_path else '❌ 否'}")
    
    # 测试单例模式
    print(f"\n🔄 测试单例模式:")
    hk_db2 = get_database_manager('HK')
    us_db2 = get_database_manager('US')
    print(f"  港股数据库单例: {'✅ 是' if hk_db is hk_db2 else '❌ 否'}")
    print(f"  美股数据库单例: {'✅ 是' if us_db is us_db2 else '❌ 否'}")
    
    print(f"\n✅ 多市场数据库测试完成!")

if __name__ == '__main__':
    test_multi_market_db()