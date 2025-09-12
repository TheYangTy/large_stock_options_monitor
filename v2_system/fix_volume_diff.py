#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正数据库中所有期权交易记录的变化量计算
使用正确的逻辑：与上一条记录比较，而不是与今日最新记录比较
"""

import os
import sys
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

# 添加V2系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import DATABASE_CONFIG
from utils.logger import setup_logger


class VolumeFixProcessor:
    """变化量修正处理器"""
    
    def __init__(self):
        self.logger = setup_logger('VolumeFixProcessor')
        self.db_path = DATABASE_CONFIG['path']
        
    def get_all_trades_by_date(self) -> Dict[str, List[Tuple]]:
        """获取所有交易记录，按日期分组"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, option_code, trade_date, volume, timestamp, volume_diff, last_volume
                    FROM option_trades 
                    ORDER BY trade_date, option_code, timestamp
                """)
                
                all_records = cursor.fetchall()
                
                # 按日期分组
                trades_by_date = {}
                for record in all_records:
                    trade_date = record[2]  # trade_date
                    if trade_date not in trades_by_date:
                        trades_by_date[trade_date] = []
                    trades_by_date[trade_date].append(record)
                
                return trades_by_date
                
        except Exception as e:
            self.logger.error(f"获取交易记录失败: {e}")
            return {}
    
    def calculate_correct_volume_diff(self, trades_by_date: Dict[str, List[Tuple]]) -> List[Tuple]:
        """计算正确的变化量"""
        updates = []
        
        for trade_date, records in trades_by_date.items():
            self.logger.info(f"处理日期: {trade_date}, 记录数: {len(records)}")
            
            # 按期权代码分组
            trades_by_option = {}
            for record in records:
                option_code = record[1]
                if option_code not in trades_by_option:
                    trades_by_option[option_code] = []
                trades_by_option[option_code].append(record)
            
            # 为每个期权计算正确的变化量
            for option_code, option_records in trades_by_option.items():
                # 按时间戳排序
                option_records.sort(key=lambda x: x[4])  # timestamp
                
                for i, record in enumerate(option_records):
                    record_id = record[0]
                    current_volume = record[3]
                    
                    if i == 0:
                        # 第一条记录，变化量就是当前成交量
                        previous_volume = 0
                        volume_diff = current_volume
                    else:
                        # 后续记录，与上一条记录比较
                        previous_record = option_records[i-1]
                        previous_volume = previous_record[3]
                        volume_diff = current_volume - previous_volume
                    
                    # 只有当计算出的值与数据库中的值不同时才更新
                    db_volume_diff = record[5]
                    db_last_volume = record[6]
                    
                    if db_volume_diff != volume_diff or db_last_volume != previous_volume:
                        updates.append((volume_diff, previous_volume, record_id))
        
        return updates
    
    def update_database(self, updates: List[Tuple]) -> bool:
        """批量更新数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.executemany("""
                    UPDATE option_trades 
                    SET volume_diff = ?, last_volume = ?
                    WHERE id = ?
                """, updates)
                
                conn.commit()
                self.logger.info(f"成功更新 {len(updates)} 条记录")
                return True
                
        except Exception as e:
            self.logger.error(f"更新数据库失败: {e}")
            return False
    
    def fix_all_volume_diff(self) -> bool:
        """修正所有变化量"""
        try:
            self.logger.info("开始修正数据库中的变化量...")
            
            # 1. 获取所有交易记录
            trades_by_date = self.get_all_trades_by_date()
            if not trades_by_date:
                self.logger.warning("没有找到交易记录")
                return False
            
            total_records = sum(len(records) for records in trades_by_date.values())
            self.logger.info(f"共找到 {total_records} 条交易记录，涉及 {len(trades_by_date)} 个交易日")
            
            # 2. 计算正确的变化量
            updates = self.calculate_correct_volume_diff(trades_by_date)
            
            if not updates:
                self.logger.info("所有记录的变化量都是正确的，无需更新")
                return True
            
            self.logger.info(f"需要更新 {len(updates)} 条记录")
            
            # 3. 更新数据库
            success = self.update_database(updates)
            
            if success:
                self.logger.info("变化量修正完成！")
            else:
                self.logger.error("变化量修正失败！")
            
            return success
            
        except Exception as e:
            self.logger.error(f"修正变化量过程中出错: {e}")
            return False
    
    def verify_fix(self) -> bool:
        """验证修正结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查是否还有异常的变化量
                cursor.execute("""
                    SELECT COUNT(*) FROM option_trades 
                    WHERE volume_diff < 0 OR volume_diff > volume
                """)
                
                abnormal_count = cursor.fetchone()[0]
                
                if abnormal_count > 0:
                    self.logger.warning(f"仍有 {abnormal_count} 条记录的变化量可能异常")
                    return False
                else:
                    self.logger.info("所有记录的变化量都正常")
                    return True
                    
        except Exception as e:
            self.logger.error(f"验证修正结果失败: {e}")
            return False


def main():
    """主函数"""
    print("=" * 60)
    print("期权交易记录变化量修正工具")
    print("=" * 60)
    
    processor = VolumeFixProcessor()
    
    # 询问用户确认
    confirm = input("是否要修正数据库中所有期权交易记录的变化量？(y/N): ")
    if confirm.lower() != 'y':
        print("操作已取消")
        return
    
    # 执行修正
    success = processor.fix_all_volume_diff()
    
    if success:
        print("\n✅ 变化量修正成功！")
        
        # 验证结果
        print("正在验证修正结果...")
        if processor.verify_fix():
            print("✅ 验证通过，所有记录的变化量都正确")
        else:
            print("⚠️  验证发现异常，请检查日志")
    else:
        print("\n❌ 变化量修正失败，请检查日志")


if __name__ == "__main__":
    main()