# -*- coding: utf-8 -*-
"""
数据处理模块
"""

import pandas as pd
import os
import logging
from typing import Dict
from config import DATA_CONFIG


class DataHandler:
    """数据处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.DataHandler')
        self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """确保数据目录存在"""
        if DATA_CONFIG['save_to_csv']:
            data_dir = os.path.dirname(DATA_CONFIG['csv_path'])
            if data_dir:
                os.makedirs(data_dir, exist_ok=True)
    
    def save_trade(self, trade_info: Dict):
        """保存交易数据"""
        if DATA_CONFIG['save_to_csv']:
            self._save_to_csv(trade_info)
        
        if DATA_CONFIG['save_to_db']:
            self._save_to_database(trade_info)
    
    def _save_to_csv(self, trade_info: Dict):
        """保存到CSV文件"""
        try:
            csv_path = DATA_CONFIG['csv_path']
            
            # 准备数据
            df_new = pd.DataFrame([trade_info])
            
            # 如果文件存在，追加数据；否则创建新文件
            if os.path.exists(csv_path):
                df_new.to_csv(csv_path, mode='a', header=False, index=False, encoding='utf-8')
            else:
                df_new.to_csv(csv_path, mode='w', header=True, index=False, encoding='utf-8')
            
            self.logger.debug(f"交易数据已保存到CSV: {trade_info['option_code']}")
            
        except Exception as e:
            self.logger.error(f"保存CSV数据失败: {e}")
    
    def _save_to_database(self, trade_info: Dict):
        """保存到数据库（可扩展）"""
        # 这里可以实现数据库存储逻辑
        # 例如：SQLite, MySQL, PostgreSQL等
        pass
    
    def load_historical_data(self, days: int = 7) -> pd.DataFrame:
        """加载历史数据"""
        try:
            if not DATA_CONFIG['save_to_csv'] or not os.path.exists(DATA_CONFIG['csv_path']):
                return pd.DataFrame()
            
            df = pd.read_csv(DATA_CONFIG['csv_path'], encoding='utf-8')
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 筛选最近几天的数据
            cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days)
            recent_data = df[df['timestamp'] >= cutoff_date]
            
            return recent_data
            
        except Exception as e:
            self.logger.error(f"加载历史数据失败: {e}")
            return pd.DataFrame()
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            df = self.load_historical_data()
            
            if df.empty:
                return {'total_trades': 0}
            
            stats = {
                'total_trades': len(df),
                'unique_stocks': df['stock_code'].nunique(),
                'unique_options': df['option_code'].nunique(),
                'total_volume': df['volume'].sum(),
                'total_turnover': df['turnover'].sum(),
                'avg_trade_size': df['volume'].mean(),
                'latest_trade_time': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {'error': str(e)}