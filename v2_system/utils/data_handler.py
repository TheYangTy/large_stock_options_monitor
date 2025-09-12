# -*- coding: utf-8 -*-
"""
V2系统数据处理模块
"""

import json
import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys

# 添加V2系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SYSTEM_CONFIG, DATABASE_CONFIG


class V2DataHandler:
    """V2系统数据处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger('V2OptionMonitor.DataHandler')
        self.cache_dir = SYSTEM_CONFIG['cache_dir']
        self.stock_info_file = SYSTEM_CONFIG['stock_info_cache']
        self.price_cache_file = SYSTEM_CONFIG['price_cache']
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.stock_info_file), exist_ok=True)
    
    def save_stock_prices(self, stock_prices: Dict[str, Any]) -> bool:
        """保存股票价格到缓存文件"""
        try:
            cache_data = {
                'update_time': datetime.now().isoformat(),
                'prices': stock_prices
            }
            
            with open(self.price_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"V2股票价格缓存已保存: {len(stock_prices)}只股票")
            return True
            
        except Exception as e:
            self.logger.error(f"V2保存股票价格缓存失败: {e}")
            return False
    
    def load_stock_prices(self) -> Dict[str, Any]:
        """从缓存文件加载股票价格"""
        try:
            if not os.path.exists(self.price_cache_file):
                return {}
            
            with open(self.price_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期（5分钟）
            update_time_str = cache_data.get('update_time')
            if update_time_str:
                update_time = datetime.fromisoformat(update_time_str)
                if (datetime.now() - update_time).seconds > 300:
                    self.logger.info("V2股票价格缓存已过期")
                    return {}
            
            prices = cache_data.get('prices', {})
            self.logger.info(f"V2从缓存加载股票价格: {len(prices)}只股票")
            return prices
            
        except Exception as e:
            self.logger.error(f"V2加载股票价格缓存失败: {e}")
            return {}
    
    def save_stock_info(self, stock_info: Dict[str, Any]) -> bool:
        """保存股票基本信息"""
        try:
            info_data = {
                'update_time': datetime.now().isoformat(),
                'stocks': stock_info
            }
            
            with open(self.stock_info_file, 'w', encoding='utf-8') as f:
                json.dump(info_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"V2股票基本信息已保存: {len(stock_info)}只股票")
            return True
            
        except Exception as e:
            self.logger.error(f"V2保存股票基本信息失败: {e}")
            return False
    
    def load_stock_info(self) -> Dict[str, Any]:
        """加载股票基本信息"""
        try:
            if not os.path.exists(self.stock_info_file):
                return {}
            
            with open(self.stock_info_file, 'r', encoding='utf-8') as f:
                info_data = json.load(f)
            
            stocks = info_data.get('stocks', {})
            self.logger.info(f"V2从缓存加载股票基本信息: {len(stocks)}只股票")
            return stocks
            
        except Exception as e:
            self.logger.error(f"V2加载股票基本信息失败: {e}")
            return {}
    
    def save_option_data(self, option_data: List[Dict[str, Any]]) -> bool:
        """保存期权数据"""
        try:
            if not option_data:
                return True
            
            # 按日期分组保存
            today = datetime.now().strftime('%Y-%m-%d')
            option_file = os.path.join(self.cache_dir, f'options_{today}.json')
            
            # 如果文件已存在，追加数据
            existing_data = []
            if os.path.exists(option_file):
                try:
                    with open(option_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except:
                    existing_data = []
            
            # 合并数据
            all_data = existing_data + option_data
            
            # 去重（基于期权代码和时间戳）
            unique_data = {}
            for item in all_data:
                key = f"{item.get('option_code')}_{item.get('timestamp')}"
                unique_data[key] = item
            
            final_data = list(unique_data.values())
            
            with open(option_file, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"V2期权数据已保存: {len(final_data)}条记录")
            return True
            
        except Exception as e:
            self.logger.error(f"V2保存期权数据失败: {e}")
            return False
    
    def load_recent_option_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """加载最近几天的期权数据"""
        try:
            all_data = []
            
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                option_file = os.path.join(self.cache_dir, f'options_{date}.json')
                
                if os.path.exists(option_file):
                    try:
                        with open(option_file, 'r', encoding='utf-8') as f:
                            daily_data = json.load(f)
                            all_data.extend(daily_data)
                    except Exception as e:
                        self.logger.warning(f"V2加载{date}期权数据失败: {e}")
            
            self.logger.info(f"V2加载最近{days}天期权数据: {len(all_data)}条记录")
            return all_data
            
        except Exception as e:
            self.logger.error(f"V2加载最近期权数据失败: {e}")
            return []
    
    def cleanup_old_data(self, keep_days: int = 30) -> bool:
        """清理旧数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            cleaned_count = 0
            
            # 清理期权数据文件
            for filename in os.listdir(self.cache_dir):
                if filename.startswith('options_') and filename.endswith('.json'):
                    try:
                        date_str = filename[8:18]  # 提取日期部分
                        file_date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        if file_date < cutoff_date:
                            file_path = os.path.join(self.cache_dir, filename)
                            os.remove(file_path)
                            cleaned_count += 1
                            self.logger.info(f"V2删除旧数据文件: {filename}")
                    except Exception as e:
                        self.logger.warning(f"V2处理文件{filename}失败: {e}")
            
            self.logger.info(f"V2数据清理完成，删除{cleaned_count}个文件")
            return True
            
        except Exception as e:
            self.logger.error(f"V2数据清理失败: {e}")
            return False
    
    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> bool:
        """导出数据到CSV文件"""
        try:
            if not data:
                return True
            
            df = pd.DataFrame(data)
            csv_file = os.path.join(self.cache_dir, filename)
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"V2数据已导出到CSV: {csv_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"V2导出CSV失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据统计信息"""
        try:
            stats = {
                'cache_dir': self.cache_dir,
                'cache_files': [],
                'total_size': 0,
                'file_count': 0
            }
            
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        stats['cache_files'].append({
                            'name': filename,
                            'size': file_size,
                            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                        })
                        stats['total_size'] += file_size
                        stats['file_count'] += 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"V2获取统计信息失败: {e}")
            return {}