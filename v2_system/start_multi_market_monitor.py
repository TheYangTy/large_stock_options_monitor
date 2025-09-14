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
    HK_MONITOR_STOCKS, 
    US_MONITOR_STOCKS,
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
        self.api_lock = threading.Lock()  # 添加API锁，防止并发请求
        self.last_api_call = 0  # 上次API调用时间戳
        self.min_api_interval = 5  # API调用最小间隔(秒)
        
    def wait_for_api_availability(self):
        """等待API可用（限流保护）"""
        with self.api_lock:
            now = time.time()
            elapsed = now - self.last_api_call
            
            if elapsed < self.min_api_interval:
                wait_time = self.min_api_interval - elapsed
                self.logger.debug(f"API限流保护：等待{wait_time:.1f}秒")
                time.sleep(wait_time)
            
            self.last_api_call = time.time()
    
    def start_hk_monitor(self):
        """启动港股监控"""
        try:
            self.logger.info("🇭🇰 启动港股期权监控线程")
            self.hk_monitor = V2OptionMonitor(market='HK')
            self.logger.info(f"📋 港股监控列表: {len(HK_MONITOR_STOCKS)} 只股票")
            
            # 港股线程先等待5秒，避免与美股线程同时启动
            self.logger.info("港股监控线程等待5秒，错峰启动...")
            time.sleep(5)
            
            # 监控循环中添加错峰机制
            scan_interval = 120  # 基础扫描间隔(秒) - 2分钟
            
            while self.running:
                try:
                    is_trading = is_hk_trading_time()
                    should_monitor = should_monitor_market('HK')
                    
                    if is_trading or should_monitor:
                        self.logger.info("🇭🇰 港股监控开始扫描...")
                        
                        # 获取API锁，确保不与美股监控同时请求API
                        self.wait_for_api_availability()
                        
                        if is_trading:
                            self.logger.info("✅ 港股交易时间，正常监控并发送所有通知")
                            self.hk_monitor.manual_scan()
                        else:
                            self.logger.info("⏰ 港股非交易时间，继续监控数据但不发送额外通知")
                            self.hk_monitor.manual_scan()
                    else:
                        self.logger.info("🔒 港股非交易时间且调试开关已关闭，跳过数据更新")
                    
                    # 添加随机延时(115-125秒)，避免与美股监控同步
                    jitter = scan_interval + (hash(f"hk_{time.time()}") % 10)
                    self.logger.info(f"港股监控等待{jitter}秒(约{jitter/60:.1f}分钟)后下次扫描")
                    time.sleep(jitter)
                    
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
            self.logger.info(f"📋 美股监控列表: {len(US_MONITOR_STOCKS)} 只股票")
            
            # 美股线程先等待60秒，确保与港股错开1分钟
            self.logger.info("美股监控线程等待60秒，错峰启动...")
            time.sleep(60)
            
            # 监控循环中添加错峰机制
            scan_interval = 120  # 基础扫描间隔(秒) - 2分钟
            
            while self.running:
                try:
                    is_trading = is_us_trading_time()
                    should_monitor = should_monitor_market('US')
                    
                    if is_trading or should_monitor:
                        self.logger.info("🇺🇸 美股监控开始扫描...")
                        
                        # 获取API锁，确保不与港股监控同时请求API
                        self.wait_for_api_availability()
                        
                        if is_trading:
                            self.logger.info("✅ 美股交易时间，正常监控并发送所有通知")
                            self.us_monitor.manual_scan()
                        else:
                            self.logger.info("⏰ 美股非交易时间，继续监控数据但不发送额外通知")
                            self.us_monitor.manual_scan()
                    else:
                        self.logger.info("🔒 美股非交易时间且调试开关已关闭，跳过数据更新")
                    
                    # 添加随机延时(115-125秒)，避免与港股监控同步
                    jitter = scan_interval + (hash(f"us_{time.time()}") % 10)
                    self.logger.info(f"美股监控等待{jitter}秒(约{jitter/60:.1f}分钟)后下次扫描")
                    time.sleep(jitter)
                    
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
        
        # 启动线程 - 先启动港股，再启动美股，确保错峰
        self.logger.info("🚀 启动港股监控线程...")
        hk_thread.start()
        
        self.logger.info("⏱️ 等待60秒(1分钟)后启动美股监控线程...")
        time.sleep(60)
        
        self.logger.info("🚀 启动美股监控线程...")
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
    logger.info("⚠️ 多市场模式已启用错峰请求机制，避免API并发失败")
    logger.info("⏱️ 单一市场轮询间隔: 2分钟，市场间间隔: 1分钟")
    
    try:
        # 显示监控配置
        logger.info("📊 监控配置:")
        logger.info(f"  🇭🇰 港股: {len(HK_MONITOR_STOCKS)} 只股票")
        for stock_code in HK_MONITOR_STOCKS:
            logger.info(f"    - {stock_code}")
        
        logger.info(f"  🇺🇸 美股: {len(US_MONITOR_STOCKS)} 只股票")
        for stock_code in US_MONITOR_STOCKS:
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