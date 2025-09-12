#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股期权监控启动脚本
支持美股期权大单监控，逻辑与港股一致
"""

import sys
import os
import time
import logging
from datetime import datetime

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from option_monitor_v2 import V2OptionMonitor
from config import (
    US_MONITOR_STOCKS, 
    is_us_trading_time,
    get_market_type,
    FUTU_CONFIG
)

# 为了兼容性，创建别名
US_STOCK_CODES = US_MONITOR_STOCKS

def setup_logging():
    """设置日志"""
    log_dir = os.path.join(current_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'us_monitor_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("🇺🇸 美股期权监控系统启动")
    
    try:
        # 检查美股交易时间
        if not is_us_trading_time():
            logger.warning("⏰ 当前非美股交易时间，但系统将继续运行以便测试")
        else:
            logger.info("✅ 当前为美股交易时间")
        
        # 显示监控的美股列表
        logger.info(f"📊 监控美股列表: {US_STOCK_CODES}")
        for stock_code in US_STOCK_CODES:
            market_type = get_market_type(stock_code)
            logger.info(f"  - {stock_code} ({market_type}市场)")
        
        # 创建监控实例
        monitor = V2OptionMonitor(market='US')
        
        # 设置为美股模式
        monitor.stock_codes = US_STOCK_CODES
        monitor.market_type = 'US'
        
        logger.info("🚀 开始美股期权监控...")
        
        # 开始监控
        monitor.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("👋 用户中断，美股期权监控系统退出")
    except Exception as e:
        logger.error(f"❌ 美股期权监控系统异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("🔚 美股期权监控系统结束")

if __name__ == "__main__":
    main()