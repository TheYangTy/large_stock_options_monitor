# -*- coding: utf-8 -*-
"""
推送记录管理器 - 用于记录已推送的大单期权，避免重复推送
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Any, Optional


class PushRecordManager:
    """推送记录管理器"""
    
    def __init__(self, record_file: str = 'data/pushed_options.json'):
        """
        初始化推送记录管理器
        
        Args:
            record_file: 记录文件路径
        """
        self.logger = logging.getLogger('OptionMonitor.PushRecordManager')
        self.record_file = record_file
        self.pushed_records = set()  # 已推送的记录ID集合
        self.last_load_time = None   # 上次加载时间
        
        # 确保目录存在
        os.makedirs(os.path.dirname(record_file), exist_ok=True)
        
        # 加载已推送记录
        self._load_records()
    
    def _load_records(self):
        """加载已推送记录"""
        try:
            if os.path.exists(self.record_file):
                with open(self.record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pushed_records = set(data.get('pushed_ids', []))
                    self.logger.info(f"已加载 {len(self.pushed_records)} 条推送记录")
            else:
                self.logger.info(f"推送记录文件不存在，将创建新文件: {self.record_file}")
                self.pushed_records = set()
            
            self.last_load_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"加载推送记录失败: {e}")
            self.pushed_records = set()
            self.last_load_time = datetime.now()
    
    def _save_records(self):
        """保存已推送记录"""
        try:
            data = {
                'update_time': datetime.now().isoformat(),
                'pushed_ids': list(self.pushed_records),
                'count': len(self.pushed_records)
            }
            
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"已保存 {len(self.pushed_records)} 条推送记录")
            
        except Exception as e:
            self.logger.error(f"保存推送记录失败: {e}")
    
    def is_pushed(self, option_id: str) -> bool:
        """
        检查期权是否已推送
        
        Args:
            option_id: 期权记录ID
            
        Returns:
            bool: 是否已推送
        """
        # 如果上次加载时间超过10分钟，重新加载记录
        if self.last_load_time and (datetime.now() - self.last_load_time).seconds > 600:
            self._load_records()
        
        return option_id in self.pushed_records
    
    def mark_as_pushed(self, option_id: str):
        """
        标记期权为已推送
        
        Args:
            option_id: 期权记录ID
        """
        self.pushed_records.add(option_id)
        # 每次标记后保存记录
        self._save_records()
    
    def mark_batch_as_pushed(self, option_ids: List[str]):
        """
        批量标记期权为已推送
        
        Args:
            option_ids: 期权记录ID列表
        """
        self.pushed_records.update(option_ids)
        # 批量标记后保存记录
        self._save_records()
    
    def filter_new_options(self, options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤出新的期权记录
        
        Args:
            options: 期权记录列表
            
        Returns:
            List[Dict[str, Any]]: 新的期权记录列表
        """
        new_options = []
        
        for option in options:
            # 生成唯一ID
            option_id = self._generate_option_id(option)
            
            # 如果未推送过，添加到新记录列表
            if not self.is_pushed(option_id):
                # 添加ID到记录中
                option['_id'] = option_id
                new_options.append(option)
        
        return new_options
    
    def _generate_option_id(self, option: Dict[str, Any]) -> str:
        """
        生成期权记录的唯一ID
        
        Args:
            option: 期权记录
            
        Returns:
            str: 唯一ID
        """
        # 使用期权代码、成交量、成交额和时间戳生成唯一ID
        option_code = option.get('option_code', '')
        volume = option.get('volume', 0)
        turnover = option.get('turnover', 0)
        timestamp = option.get('timestamp', '')
        
        # 生成唯一ID
        option_id = f"{option_code}_{volume}_{int(turnover)}_{timestamp}"
        
        return option_id
    
    def clean_old_records(self, days: int = 7):
        """
        清理旧记录
        
        Args:
            days: 保留天数，默认7天
        """
        try:
            if not os.path.exists(self.record_file):
                return
            
            with open(self.record_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 获取更新时间
            update_time_str = data.get('update_time', '')
            if not update_time_str:
                return
            
            update_time = datetime.fromisoformat(update_time_str)
            cutoff_time = datetime.now() - timedelta(days=days)
            
            # 如果记录文件超过保留天数，清空记录
            if update_time < cutoff_time:
                self.logger.info(f"清理 {days} 天前的推送记录")
                self.pushed_records = set()
                self._save_records()
        
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")