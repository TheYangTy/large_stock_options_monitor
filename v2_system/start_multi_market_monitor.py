#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多市场期权监控启动脚本
同时支持港股和美股期权大单监控
"""

import sys
import os
import time
import logging
import threading
from datetime import datetime
from typing import List

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from option_monitor_v2 import V2OptionMonitor
from config import (
    STOCK_CODES, 
    US_STOCK_CODES,
    is_hk_trading_time,
    is_us_trading_time,
    get_market_type,
    should_monitor_market,
    should_update_data_off_hours,
    FUTU_CONFIG
)

def setup_logging():
    """设置日志"""
    log_dir = os.path.join(current_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'multi_market_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

class MultiMarketMonitor:
    """多市场期权监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.hk_monitor = None
        self.us_monitor = None
        self.running = False
        
    def start_hk_monitor(self):
        """启动港股监控"""
        try:
            self.logger.info("🇭🇰 启动港股期权监控线程")
            self.hk_monitor = V2OptionMonitor(market='HK')
            self.logger.info(f"📋 港股监控列表: {len(STOCK_CODES)} 只股票")
            
            while self.running:
                try:
                    is_trading = is_hk_trading_time()
                    should_monitor = should_monitor_market('HK')
                    
                    if is_trading:
                        self.logger.info("✅ 港股交易时间，正常监控并发送所有通知")
                        self.hk_monitor.manual_scan()
                    elif should_monitor:
                        self.logger.info("⏰ 港股非交易时间，继续监控数据但不发送额外通知")
                        self.hk_monitor.manual_scan()
                    else:
                        self.logger.info("🔒 港股非交易时间且调试开关已关闭，跳过数据更新")
                    
                    # 每30秒检查一次
                    time.sleep(30)
                    
                except Exception as e:
                    self.logger.error(f"❌ 港股监控异常: {e}")
                    time.sleep(60)  # 异常时等待1分钟
                    
        except Exception as e:
            self.logger.error(f"❌ 港股监控线程异常: {e}")
    
    def start_us_monitor(self):
        """启动美股监控"""
        try:
            self.logger.info("🇺🇸 启动美股期权监控线程")
            self.us_monitor = V2OptionMonitor(market='US')
            self.logger.info(f"📋 美股监控列表: {len(US_STOCK_CODES)} 只股票")
            
            while self.running:
                try:
                    is_trading = is_us_trading_time()
                    should_monitor = should_monitor_market('US')
                    
                    if is_trading:
                        self.logger.info("✅ 美股交易时间，正常监控并发送所有通知")
                        self.us_monitor.manual_scan()
                    elif should_monitor:
                        self.logger.info("⏰ 美股非交易时间，继续监控数据但不发送额外通知")
                        self.us_monitor.manual_scan()
                    else:
                        self.logger.info("🔒 美股非交易时间且调试开关已关闭，跳过数据更新")
                    
                    # 每30秒检查一次
                    time.sleep(30)
                    
                except Exception as e:
                    self.logger.error(f"❌ 美股监控异常: {e}")
                    time.sleep(60)  # 异常时等待1分钟
                    
        except Exception as e:
            self.logger.error(f"❌ 美股监控线程异常: {e}")
    
    def start_monitoring(self):
        """开始多市场监控"""
        self.running = True
        
        # 创建监控线程
        hk_thread = threading.Thread(target=self.start_hk_monitor, name="HK-Monitor")
        us_thread = threading.Thread(target=self.start_us_monitor, name="US-Monitor")
        
        # 设置为守护线程
        hk_thread.daemon = True
        us_thread.daemon = True
        
        # 启动线程
        hk_thread.start()
        us_thread.start()
        
        self.logger.info("🚀 多市场期权监控已启动")
        
        try:
            # 主线程保持运行
            while self.running:
                # 每10分钟输出一次状态
                time.sleep(600)
                hk_status = "运行中" if hk_thread.is_alive() else "已停止"
                us_status = "运行中" if us_thread.is_alive() else "已停止"
                self.logger.info(f"📊 监控状态 - 港股: {hk_status}, 美股: {us_status}")
                
                # 检查线程是否还活着，如果死了就重启
                if not hk_thread.is_alive():
                    self.logger.warning("🔄 港股监控线程已停止，重新启动...")
                    hk_thread = threading.Thread(target=self.start_hk_monitor, name="HK-Monitor")
                    hk_thread.daemon = True
                    hk_thread.start()
                
                if not us_thread.is_alive():
                    self.logger.warning("🔄 美股监控线程已停止，重新启动...")
                    us_thread = threading.Thread(target=self.start_us_monitor, name="US-Monitor")
                    us_thread.daemon = True
                    us_thread.start()
                    
        except KeyboardInterrupt:
            self.logger.info("👋 用户中断，停止监控")
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        self.logger.info("🛑 多市场期权监控已停止")

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("🌍 多市场期权监控系统启动")
    
    try:
        # 显示监控配置
        logger.info("📊 监控配置:")
        logger.info(f"  🇭🇰 港股: {len(STOCK_CODES)} 只股票")
        for stock_code in STOCK_CODES:
            logger.info(f"    - {stock_code}")
        
        logger.info(f"  🇺🇸 美股: {len(US_STOCK_CODES)} 只股票")
        for stock_code in US_STOCK_CODES:
            logger.info(f"    - {stock_code}")
        
        # 检查当前交易时间
        hk_trading = is_hk_trading_time()
        us_trading = is_us_trading_time()
        
        logger.info(f"⏰ 当前交易状态:")
        logger.info(f"  🇭🇰 港股: {'交易中' if hk_trading else '休市'}")
        logger.info(f"  🇺🇸 美股: {'交易中' if us_trading else '休市'}")
        
        if not hk_trading and not us_trading:
            logger.warning("⚠️  当前两个市场都在休市，但系统将继续运行")
        
        # 创建并启动多市场监控
        monitor = MultiMarketMonitor()
        monitor.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("👋 用户中断，多市场期权监控系统退出")
    except Exception as e:
        logger.error(f"❌ 多市场期权监控系统异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("🔚 多市场期权监控系统结束")

if __name__ == "__main__":
    main()