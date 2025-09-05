# -*- coding: utf-8 -*-
"""
日志配置模块
"""

import logging
import logging.handlers
import os
from config import LOG_CONFIG


def setup_logger(name='OptionMonitor'):
    """设置日志记录器"""
    
    # 创建日志目录
    log_dir = os.path.dirname(LOG_CONFIG['log_file'])
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_CONFIG['log_level']))
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 创建formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件handler (带轮转)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_CONFIG['log_file'],
        maxBytes=LOG_CONFIG['max_file_size'],
        backupCount=LOG_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOG_CONFIG['log_level']))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger