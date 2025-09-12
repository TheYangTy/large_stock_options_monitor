# -*- coding: utf-8 -*-
"""
V2系统港股期权大单监控主程序 - 完全独立版本
"""

import time
import logging
import traceback
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import signal
import sys
import os
import argparse

# 添加V2系统路径 - 支持从根目录启动
current_dir = os.path.dirname(os.path.abspath(__file__))
v2_system_dir = current_dir if current_dir.endswith('v2_system') else os.path.join(current_dir, 'v2_system')
sys.path.insert(0, v2_system_dir)

# 设置工作目录为v2_system
if not os.getcwd().endswith('v2_system'):
    v2_work_dir = v2_system_dir
    os.chdir(v2_work_dir)
    print(f"V2系统工作目录已切换到: {v2_work_dir}")

# 第三方库
try:
    import futu as ft
    import json
except ImportError as e:
    print(f"请安装必要的依赖包: {e}")
    print("pip install futu-api pandas numpy scipy flask requests")
    sys.exit(1)

from config import *
from utils.logger import setup_logger
from utils.notifier import V2Notifier
from utils.data_handler import V2DataHandler
from utils.mac_notifier import MacNotifier
from utils.big_options_processor import BigOptionsProcessor


class V2OptionMonitor:
    """V2系统港股期权大单监控器"""
    
    def __init__(self):
        self.logger = setup_logger('V2OptionMonitor')
        self.notifier = V2Notifier()
        self.data_handler = V2DataHandler()
        self.mac_notifier = MacNotifier()
        self.big_options_processor = BigOptionsProcessor()
        self.quote_ctx = None
        self.is_running = False
        self.monitor_thread = None
        self.subscribed_options = set()  # 已订阅的期权代码
        self.stock_price_cache = {}  # 股价缓存
        self.price_update_time = {}  # 股价更新时间
        self.option_chain_cache = {}  # 期权链缓存
        self.last_scan_time = None
        self.scan_count = 0
        
        self.logger.info("V2系统期权监控器初始化完成")
    
    def connect_futu(self) -> bool:
        """连接富途OpenD"""
        try:
            self.quote_ctx = ft.OpenQuoteContext(
                host=FUTU_CONFIG['host'], 
                port=FUTU_CONFIG['port']
            )
            
            # 测试连接
            ret, data = self.quote_ctx.get_market_snapshot(['HK.00700'])
            if ret == ft.RET_OK:
                self.logger.info(f"V2系统富途OpenD连接成功: {FUTU_CONFIG['host']}:{FUTU_CONFIG['port']}")
                return True
            else:
                self.logger.error(f"V2系统富途OpenD连接测试失败: {ret}")
                return False
                
        except Exception as e:
            self.logger.error(f"V2系统连接富途OpenD失败: {e}")
            return False
    
    def disconnect_futu(self):
        """断开富途连接"""
        try:
            if self.quote_ctx:
                self.quote_ctx.close()
                self.logger.info("V2系统富途OpenD连接已断开")
        except Exception as e:
            self.logger.error(f"V2系统断开富途连接失败: {e}")
    
    def get_stock_price(self, stock_code: str) -> float:
        """获取股票价格（带缓存）"""
        try:
            current_time = datetime.now()
            
            # 检查缓存
            if (stock_code in self.stock_price_cache and 
                stock_code in self.price_update_time and
                (current_time - self.price_update_time[stock_code]).seconds < 300):  # 5分钟缓存
                return self.stock_price_cache[stock_code]
            
            # 获取实时价格
            ret, data = self.quote_ctx.get_market_snapshot([stock_code])
            if ret == ft.RET_OK and not data.empty:
                price = float(data.iloc[0]['last_price'])
                self.stock_price_cache[stock_code] = price
                self.price_update_time[stock_code] = current_time
                return price
            else:
                # 使用默认价格
                default_prices = {
                    'HK.00700': 600.0, 'HK.09988': 80.0, 'HK.03690': 120.0,
                    'HK.01810': 15.0, 'HK.09618': 120.0, 'HK.02318': 40.0,
                    'HK.00388': 300.0, 'HK.00981': 60.0, 'HK.01024': 50.0
                }
                return default_prices.get(stock_code, 100.0)
                
        except Exception as e:
            self.logger.error(f"V2系统获取{stock_code}股价失败: {e}")
            return 100.0  # 默认价格
    
    def scan_big_options(self) -> List[Dict]:
        """扫描大单期权"""
        try:
            self.scan_count += 1
            self.logger.info(f"V2系统开始第{self.scan_count}次大单期权扫描...")
            
            # 获取大单期权
            big_options = self.big_options_processor.get_recent_big_options(
                self.quote_ctx, 
                MONITOR_STOCKS,
                option_monitor=self
            )
            
            if big_options:
                self.logger.info(f"V2系统发现 {len(big_options)} 笔大单期权")
                
                # 保存数据
                self.data_handler.save_option_data(big_options)
                self.big_options_processor.save_big_options_summary(big_options)
                
                # 发送按股票汇总的通知
                if big_options:
                    self.notifier.send_stock_grouped_notifications(big_options)
                
            else:
                self.logger.info("V2系统本次扫描未发现大单期权")
            
            self.last_scan_time = datetime.now()
            return big_options
            
        except Exception as e:
            self.logger.error(f"V2系统扫描大单期权失败: {e}")
            self.logger.error(traceback.format_exc())
            return []
    
    def monitor_loop(self):
        """监控主循环"""
        self.logger.info("V2系统监控循环开始")
        
        while self.is_running:
            try:
                # 检查是否在交易时间,true为测试用
                if True or self.is_trading_time():
                    # 扫描大单期权
                    big_options = self.scan_big_options()
                    
                    # 等待下次扫描
                    time.sleep(SYSTEM_CONFIG['monitor_interval'])
                else:
                    self.logger.info("V2系统非交易时间，暂停监控")
                    time.sleep(60)  # 非交易时间每分钟检查一次
                    
            except KeyboardInterrupt:
                self.logger.info("V2系统收到中断信号，停止监控")
                break
            except Exception as e:
                self.logger.error(f"V2系统监控循环异常: {e}")
                self.logger.error(traceback.format_exc())
                time.sleep(10)  # 异常后等待10秒再继续
    
    def is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        try:
            now = datetime.now()
            current_time = now.strftime('%H:%M')
            
            # 检查是否是工作日（周一到周五）
            if now.weekday() >= 5:  # 周六日
                return False
            
            # 检查是否在交易时间段
            market_open = TRADING_HOURS['market_open']
            market_close = TRADING_HOURS['market_close']
            lunch_start = TRADING_HOURS['lunch_break_start']
            lunch_end = TRADING_HOURS['lunch_break_end']
            
            # 上午时段：09:30-12:00
            if market_open <= current_time < lunch_start:
                return True
            
            # 下午时段：13:00-16:00
            if lunch_end <= current_time < market_close:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"V2系统检查交易时间失败: {e}")
            return True  # 异常时默认为交易时间
    
    def start_monitoring(self):
        """启动监控"""
        try:
            if self.is_running:
                self.logger.warning("V2系统监控已在运行中")
                return
            
            # 连接富途
            if not self.connect_futu():
                self.logger.error("V2系统无法连接富途OpenD，监控启动失败")
                return
            
            self.is_running = True
            
            # 启动监控线程
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            self.logger.info("V2系统期权监控已启动")
            
            # 发送启动通知
            self.notifier.send_wework_notification("V2系统期权大单监控已启动")
            self.mac_notifier.send_notification("V2系统启动", "期权大单监控已开始运行")
            
        except Exception as e:
            self.logger.error(f"V2系统启动监控失败: {e}")
            self.logger.error(traceback.format_exc())
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            if not self.is_running:
                self.logger.warning("V2系统监控未在运行")
                return
            
            self.is_running = False
            
            # 等待监控线程结束
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            # 断开富途连接
            self.disconnect_futu()
            
            self.logger.info("V2系统期权监控已停止")
            
            # 发送停止通知
            self.notifier.send_wework_notification("V2系统期权大单监控已停止")
            
        except Exception as e:
            self.logger.error(f"V2系统停止监控失败: {e}")
    
    def get_status(self) -> Dict:
        """获取监控状态"""
        return {
            'is_running': self.is_running,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_count': self.scan_count,
            'subscribed_options': len(self.subscribed_options),
            'cached_stocks': len(self.stock_price_cache),
            'is_trading_time': self.is_trading_time(),
            'system_version': 'V2'
        }
    
    def manual_scan(self) -> List[Dict]:
        """手动扫描一次"""
        self.logger.info("V2系统执行手动扫描...")
        if not self.quote_ctx:
            if not self.connect_futu():
                self.logger.error("V2系统无法连接富途OpenD")
                return []
        
        return self.scan_big_options()


def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\nV2系统收到信号 {signum}，正在优雅退出...")
    if 'monitor' in globals():
        monitor.stop_monitoring()
    sys.exit(0)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='V2系统港股期权大单监控')
    parser.add_argument('--mode', choices=['monitor', 'scan', 'status', 'test'], 
                       default='monitor', help='运行模式')
    parser.add_argument('--config-check', action='store_true', help='检查配置')
    
    args = parser.parse_args()
    
    # 配置检查
    if args.config_check:
        errors = validate_config()
        if errors:
            print("V2系统配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("V2系统配置验证通过")
            return 0
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建监控器
    global monitor
    monitor = V2OptionMonitor()
    
    try:
        if args.mode == 'monitor':
            # 持续监控模式
            monitor.start_monitoring()
            
            # 保持主线程运行
            try:
                while monitor.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            
        elif args.mode == 'scan':
            # 单次扫描模式
            big_options = monitor.manual_scan()
            print(f"V2系统扫描完成，发现 {len(big_options)} 笔大单期权")
            
            if big_options:
                for i, option in enumerate(big_options[:5], 1):  # 显示前5个
                    print(f"{i}. {option.get('stock_name')} {option.get('option_code')} "
                          f"成交额: {option.get('turnover', 0):,.0f}港币")
            
        elif args.mode == 'status':
            # 状态查看模式
            status = monitor.get_status()
            print("V2系统监控状态:")
            for key, value in status.items():
                print(f"  {key}: {value}")
                
        elif args.mode == 'test':
            # 测试模式
            print("V2系统测试模式...")
            if monitor.connect_futu():
                print("✓ 富途连接正常")
                
                # 测试获取股价
                test_stock = 'HK.00700'
                price = monitor.get_stock_price(test_stock)
                print(f"✓ 获取股价正常: {test_stock} = {price}")
                
                # 测试通知
                monitor.notifier.send_wework_notification("V2系统测试通知")
                monitor.mac_notifier.send_notification("V2测试", "系统测试通知")
                print("✓ 通知功能测试完成")
                
                monitor.disconnect_futu()
            else:
                print("✗ 富途连接失败")
                return 1
    
    except Exception as e:
        print(f"V2系统运行异常: {e}")
        traceback.print_exc()
        return 1
    
    finally:
        if monitor.is_running:
            monitor.stop_monitoring()
    
    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)