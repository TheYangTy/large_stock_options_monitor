# -*- coding: utf-8 -*-
"""
数据库管理器 - 负责期权数据的存储和查询
"""

import sqlite3
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd
from contextlib import contextmanager


@dataclass
class OptionRecord:
    """期权记录数据结构"""
    id: Optional[int] = None
    timestamp: datetime = None
    stock_code: str = ""
    stock_name: str = ""
    stock_price: float = 0.0
    option_code: str = ""
    option_type: str = ""  # Call/Put
    strike_price: float = 0.0
    expiry_date: str = ""
    option_price: float = 0.0
    volume: int = 0
    turnover: float = 0.0
    direction: str = ""  # BUY/SELL/NEUTRAL
    change_rate: float = 0.0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    time_value: float = 0.0
    intrinsic_value: float = 0.0
    moneyness: str = ""  # ITM/ATM/OTM
    days_to_expiry: int = 0
    volume_diff: int = 0
    last_volume: int = 0
    is_big_trade: bool = False
    risk_level: str = ""
    importance_score: int = 0
    raw_data: str = ""  # JSON格式的原始数据


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/options_monitor.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('OptionMonitor.DatabaseManager')
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with self._get_connection() as conn:
                # 创建期权记录表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS option_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT,
                        stock_price REAL,
                        option_code TEXT NOT NULL,
                        option_type TEXT,
                        strike_price REAL,
                        expiry_date TEXT,
                        option_price REAL,
                        volume INTEGER,
                        turnover REAL,
                        direction TEXT,
                        change_rate REAL,
                        implied_volatility REAL,
                        delta REAL,
                        gamma REAL,
                        theta REAL,
                        vega REAL,
                        time_value REAL,
                        intrinsic_value REAL,
                        moneyness TEXT,
                        days_to_expiry INTEGER,
                        volume_diff INTEGER,
                        last_volume INTEGER,
                        is_big_trade BOOLEAN,
                        risk_level TEXT,
                        importance_score INTEGER,
                        raw_data TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON option_records(timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stock_code ON option_records(stock_code)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_option_code ON option_records(option_code)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_is_big_trade ON option_records(is_big_trade)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_expiry_date ON option_records(expiry_date)')
                
                # 创建股票价格历史表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS stock_price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT,
                        price REAL NOT NULL,
                        volume INTEGER,
                        turnover REAL,
                        change_rate REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stock_price_timestamp ON stock_price_history(timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stock_price_code ON stock_price_history(stock_code)')
                
                # 创建期权链快照表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS option_chain_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        stock_code TEXT NOT NULL,
                        expiry_date TEXT NOT NULL,
                        snapshot_data TEXT NOT NULL,  -- JSON格式的期权链数据
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('CREATE INDEX IF NOT EXISTS idx_chain_timestamp ON option_chain_snapshots(timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_chain_stock ON option_chain_snapshots(stock_code)')
                
                conn.commit()
                self.logger.info("数据库初始化完成")
                
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise
            
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
                
    def save_option_record(self, record: OptionRecord) -> int:
        """保存期权记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 准备数据
                data = asdict(record)
                data.pop('id', None)  # 移除id字段，让数据库自动生成
                
                # 处理datetime字段
                if isinstance(data['timestamp'], datetime):
                    data['timestamp'] = data['timestamp'].isoformat()
                elif data['timestamp'] is None:
                    data['timestamp'] = datetime.now().isoformat()
                    
                # 构建SQL
                columns = list(data.keys())
                placeholders = ['?' for _ in columns]
                values = list(data.values())
                
                sql = f'''
                    INSERT INTO option_records ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                '''
                
                cursor.execute(sql, values)
                record_id = cursor.lastrowid
                conn.commit()
                
                self.logger.debug(f"保存期权记录: {record.option_code}, ID: {record_id}")
                return record_id
                
        except Exception as e:
            self.logger.error(f"保存期权记录失败: {e}")
            raise
            
    def save_stock_price(self, stock_code: str, stock_name: str, price: float, 
                        volume: int = 0, turnover: float = 0.0, change_rate: float = 0.0):
        """保存股票价格历史"""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO stock_price_history 
                    (timestamp, stock_code, stock_name, price, volume, turnover, change_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (datetime.now().isoformat(), stock_code, stock_name, price, volume, turnover, change_rate))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"保存股票价格失败: {e}")
            
    def save_option_chain_snapshot(self, stock_code: str, expiry_date: str, chain_data: List[Dict]):
        """保存期权链快照"""
        try:
            with self._get_connection() as conn:
                snapshot_json = json.dumps(chain_data, ensure_ascii=False, default=str)
                conn.execute('''
                    INSERT INTO option_chain_snapshots 
                    (timestamp, stock_code, expiry_date, snapshot_data)
                    VALUES (?, ?, ?, ?)
                ''', (datetime.now().isoformat(), stock_code, expiry_date, snapshot_json))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"保存期权链快照失败: {e}")
            
    def get_big_trades(self, hours: int = 24, stock_codes: List[str] = None) -> List[OptionRecord]:
        """获取大单交易记录"""
        try:
            with self._get_connection() as conn:
                # 构建查询条件
                where_conditions = ["is_big_trade = 1"]
                params = []
                
                # 时间条件
                cutoff_time = datetime.now() - timedelta(hours=hours)
                where_conditions.append("timestamp >= ?")
                params.append(cutoff_time.isoformat())
                
                # 股票代码条件
                if stock_codes:
                    placeholders = ','.join(['?' for _ in stock_codes])
                    where_conditions.append(f"stock_code IN ({placeholders})")
                    params.extend(stock_codes)
                    
                sql = f'''
                    SELECT * FROM option_records 
                    WHERE {' AND '.join(where_conditions)}
                    ORDER BY timestamp DESC, importance_score DESC
                '''
                
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                
                # 转换为OptionRecord对象
                records = []
                for row in rows:
                    record = OptionRecord()
                    for key in row.keys():
                        if hasattr(record, key):
                            value = row[key]
                            if key == 'timestamp' and isinstance(value, str):
                                value = datetime.fromisoformat(value)
                            setattr(record, key, value)
                    records.append(record)
                    
                return records
                
        except Exception as e:
            self.logger.error(f"查询大单交易失败: {e}")
            return []
            
    def get_option_history(self, option_code: str, days: int = 7) -> List[OptionRecord]:
        """获取特定期权的历史记录"""
        try:
            with self._get_connection() as conn:
                cutoff_time = datetime.now() - timedelta(days=days)
                cursor = conn.execute('''
                    SELECT * FROM option_records 
                    WHERE option_code = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (option_code, cutoff_time.isoformat()))
                
                rows = cursor.fetchall()
                records = []
                for row in rows:
                    record = OptionRecord()
                    for key in row.keys():
                        if hasattr(record, key):
                            value = row[key]
                            if key == 'timestamp' and isinstance(value, str):
                                value = datetime.fromisoformat(value)
                            setattr(record, key, value)
                    records.append(record)
                    
                return records
                
        except Exception as e:
            self.logger.error(f"查询期权历史失败: {e}")
            return []
            
    def get_stock_price_history(self, stock_code: str, hours: int = 24) -> pd.DataFrame:
        """获取股票价格历史"""
        try:
            with self._get_connection() as conn:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                df = pd.read_sql_query('''
                    SELECT * FROM stock_price_history 
                    WHERE stock_code = ? AND timestamp >= ?
                    ORDER BY timestamp
                ''', conn, params=(stock_code, cutoff_time.isoformat()))
                
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                return df
                
        except Exception as e:
            self.logger.error(f"查询股票价格历史失败: {e}")
            return pd.DataFrame()
            
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with self._get_connection() as conn:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                
                # 基本统计
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(CASE WHEN is_big_trade = 1 THEN 1 END) as big_trades,
                        COUNT(DISTINCT stock_code) as unique_stocks,
                        COUNT(DISTINCT option_code) as unique_options,
                        SUM(CASE WHEN is_big_trade = 1 THEN volume ELSE 0 END) as total_big_volume,
                        SUM(CASE WHEN is_big_trade = 1 THEN turnover ELSE 0 END) as total_big_turnover
                    FROM option_records 
                    WHERE timestamp >= ?
                ''', (cutoff_time.isoformat(),))
                
                stats = dict(cursor.fetchone())
                
                # 按股票统计
                cursor = conn.execute('''
                    SELECT 
                        stock_code,
                        stock_name,
                        COUNT(*) as trade_count,
                        SUM(CASE WHEN is_big_trade = 1 THEN volume ELSE 0 END) as big_volume,
                        SUM(CASE WHEN is_big_trade = 1 THEN turnover ELSE 0 END) as big_turnover
                    FROM option_records 
                    WHERE timestamp >= ? AND is_big_trade = 1
                    GROUP BY stock_code, stock_name
                    ORDER BY big_turnover DESC
                ''', (cutoff_time.isoformat(),))
                
                stock_stats = [dict(row) for row in cursor.fetchall()]
                stats['by_stock'] = stock_stats
                
                return stats
                
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}
            
    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        try:
            with self._get_connection() as conn:
                cutoff_time = datetime.now() - timedelta(days=days)
                
                # 清理期权记录
                cursor = conn.execute('''
                    DELETE FROM option_records 
                    WHERE timestamp < ? AND is_big_trade = 0
                ''', (cutoff_time.isoformat(),))
                
                deleted_options = cursor.rowcount
                
                # 清理股票价格历史（保留每小时一条）
                conn.execute('''
                    DELETE FROM stock_price_history 
                    WHERE timestamp < ? AND id NOT IN (
                        SELECT MIN(id) FROM stock_price_history 
                        WHERE timestamp < ?
                        GROUP BY stock_code, strftime('%Y-%m-%d %H', timestamp)
                    )
                ''', (cutoff_time.isoformat(), cutoff_time.isoformat()))
                
                deleted_prices = cursor.rowcount
                
                # 清理期权链快照
                conn.execute('''
                    DELETE FROM option_chain_snapshots 
                    WHERE timestamp < ?
                ''', (cutoff_time.isoformat(),))
                
                deleted_chains = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"清理完成: 期权记录 {deleted_options}, 价格记录 {deleted_prices}, 链快照 {deleted_chains}")
                
        except Exception as e:
            self.logger.error(f"清理旧数据失败: {e}")
            
    def export_data(self, start_date: datetime, end_date: datetime, 
                   output_path: str, format: str = 'csv'):
        """导出数据"""
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query('''
                    SELECT * FROM option_records 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                ''', conn, params=(start_date.isoformat(), end_date.isoformat()))
                
                if format.lower() == 'csv':
                    df.to_csv(output_path, index=False, encoding='utf-8')
                elif format.lower() == 'excel':
                    df.to_excel(output_path, index=False)
                elif format.lower() == 'json':
                    df.to_json(output_path, orient='records', date_format='iso')
                    
                self.logger.info(f"数据导出完成: {output_path}, 共 {len(df)} 条记录")
                
        except Exception as e:
            self.logger.error(f"导出数据失败: {e}")