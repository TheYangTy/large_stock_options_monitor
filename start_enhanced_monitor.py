#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版期权监控启动脚本
集成企微机器人通知功能
"""

import sys
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_option_processor import EnhancedOptionProcessor
from utils.wework_notifier import WeWorkNotifier
from utils.mac_notifier import MacNotifier
from utils.logger import setup_logger
from config import *

class EnhancedOptionMonitor:
    """增强版期权监控器"""
    
    def __init__(self):
        """初始化监控器"""
        self.logger = setup_logger()
        self.processor = EnhancedOptionProcessor()
        
        # 初始化通知器
        self.mac_notifier = None
        self.wework_notifier = None
        
        if NOTIFICATION.get('enable_mac_notification', False):
            self.mac_notifier = MacNotifier()
        
        if NOTIFICATION.get('enable_wework_bot', False):
            wework_config = NOTIFICATION.get('wework_config', {})
            webhook_url = wework_config.get('webhook_url', '')
            if webhook_url:
                self.wework_notifier = WeWorkNotifier(
                    webhook_url=webhook_url,
                    mentioned_list=wework_config.get('mentioned_list', []),
                    mentioned_mobile_list=wework_config.get('mentioned_mobile_list', [])
                )
        
        self.is_running = False
        self.last_summary_time = None
    
    def start_monitoring(self):
        """启动监控"""
        self.logger.info("🚀 启动增强版港股期权监控系统")
        
        # 测试通知功能
        self._test_notifications()
        
        self.is_running = True
        
        try:
            while self.is_running:
                self._monitor_cycle()
                time.sleep(MONITOR_TIME.get('interval', 30))
                
        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在关闭监控...")
            self.is_running = False
        except Exception as e:
            self.logger.error(f"监控异常: {e}")
            self.is_running = False
    
    def _test_notifications(self):
        """测试通知功能"""
        self.logger.info("测试通知功能...")
        
        # 测试Mac通知
        if self.mac_notifier:
            try:
                self.mac_notifier.send_notification(
                    "港股期权监控系统",
                    "系统启动成功，开始监控期权大单"
                )
                self.logger.info("✅ Mac通知测试成功")
            except Exception as e:
                self.logger.error(f"❌ Mac通知测试失败: {e}")
        
        # 测试企微通知
        if self.wework_notifier:
            try:
                success = self.wework_notifier.test_connection()
                if success:
                    self.logger.info("✅ 企微机器人通知测试成功")
                else:
                    self.logger.error("❌ 企微机器人通知测试失败")
            except Exception as e:
                self.logger.error(f"❌ 企微机器人通知测试异常: {e}")
    
    def _monitor_cycle(self):
        """监控周期"""
        try:
            current_time = datetime.now()
            
            # 检查是否在交易时间
            if not self._is_trading_time(current_time):
                self.logger.debug("非交易时间，跳过监控")
                return
            
            self.logger.info(f"开始监控周期: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 获取期权大单数据（这里需要实际的数据获取逻辑）
            big_options = self._get_mock_big_options()  # 临时使用模拟数据
            
            if not big_options:
                self.logger.debug("未发现期权大单")
                return
            
            # 增强数据处理
            enhanced_options = []
            for option in big_options:
                enhanced_option = self.processor.enhance_option_data(option)
                enhanced_options.append(enhanced_option)
                
                # 检查是否需要发送通知
                if self.processor.should_notify(enhanced_option):
                    self._send_option_alert(enhanced_option)
            
            # 保存增强数据
            if enhanced_options:
                self.processor.save_enhanced_data(enhanced_options)
                self.logger.info(f"处理了 {len(enhanced_options)} 条期权大单")
            
            # 每小时发送汇总报告
            self._check_and_send_summary(enhanced_options)
            
        except Exception as e:
            self.logger.error(f"监控周期异常: {e}")
    
    def _get_mock_big_options(self) -> List[Dict[str, Any]]:
        """
        获取模拟期权大单数据
        实际使用时需要替换为真实的数据获取逻辑
        """
        # 这里返回一些模拟数据用于测试
        mock_data = [
            {
                'stock_code': 'HK.00700',
                'stock_name': '腾讯控股',
                'option_code': 'HK.TCH241220C400',
                'volume': 150,
                'price': 12.5,
                'trade_direction': 'BUY',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'stock_code': 'HK.09988',
                'stock_name': '阿里巴巴-SW',
                'option_code': 'HK.ALB241220P90',
                'volume': 200,
                'price': 8.3,
                'trade_direction': 'SELL',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]
        
        # 随机返回数据，模拟实际监控
        import random
        if random.random() < 0.3:  # 30%概率有大单
            return mock_data
        else:
            return []
    
    def _send_option_alert(self, option_data: Dict[str, Any]):
        """发送期权大单提醒"""
        try:
            message = self.processor.format_option_alert_message(option_data)
            
            # Mac通知
            if self.mac_notifier:
                title = f"期权大单: {option_data.get('stock_name', 'Unknown')}"
                subtitle = f"{option_data.get('option_type', '')} {option_data.get('direction', '')}"
                self.mac_notifier.send_notification(title, subtitle)
            
            # 企微通知
            if self.wework_notifier:
                self.wework_notifier.send_big_option_alert(option_data)
            
            self.logger.info(f"已发送期权大单提醒: {option_data.get('option_code', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"发送期权提醒失败: {e}")
    
    def _check_and_send_summary(self, options: List[Dict[str, Any]]):
        """检查并发送汇总报告"""
        try:
            current_time = datetime.now()
            
            # 每小时发送一次汇总
            if (self.last_summary_time is None or 
                (current_time - self.last_summary_time).seconds >= 3600):
                
                if options:
                    self._send_summary_report(options)
                    self.last_summary_time = current_time
                    
        except Exception as e:
            self.logger.error(f"发送汇总报告失败: {e}")
    
    def _send_summary_report(self, options: List[Dict[str, Any]]):
        """发送汇总报告"""
        try:
            # 构建汇总数据
            summary_data = {
                'trades': options,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 企微汇总报告
            if self.wework_notifier:
                self.wework_notifier.send_summary_report(summary_data)
            
            self.logger.info(f"已发送汇总报告，包含 {len(options)} 条记录")
            
        except Exception as e:
            self.logger.error(f"发送汇总报告失败: {e}")
    
    def _is_trading_time(self, current_time: datetime) -> bool:
        """检查是否在交易时间"""
        try:
            # 检查是否为工作日
            if current_time.weekday() >= 5:  # 周六日
                return False
            
            # 检查时间范围
            start_time = datetime.strptime(MONITOR_TIME.get('start_time', '09:30:00'), '%H:%M:%S').time()
            end_time = datetime.strptime(MONITOR_TIME.get('end_time', '16:00:00'), '%H:%M:%S').time()
            
            current_time_only = current_time.time()
            
            return start_time <= current_time_only <= end_time
            
        except Exception as e:
            self.logger.error(f"检查交易时间失败: {e}")
            return True  # 出错时默认允许监控
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        self.logger.info("监控已停止")


def main():
    """主函数"""
    print("🚀 启动增强版港股期权监控系统")
    print("=" * 50)
    
    # 显示配置信息
    print(f"📊 监控股票: {len(MONITOR_STOCKS)} 只")
    print(f"⏰ 监控间隔: {MONITOR_TIME.get('interval', 30)} 秒")
    print(f"💰 最小金额: {OPTION_FILTER.get('min_turnover', 50000)} 港币")
    print(f"📦 最小成交量: {OPTION_FILTER.get('min_volume', 100)} 手")
    
    # 通知配置
    notifications = []
    if NOTIFICATION.get('enable_console', False):
        notifications.append("控制台")
    if NOTIFICATION.get('enable_mac_notification', False):
        notifications.append("Mac通知")
    if NOTIFICATION.get('enable_wework_bot', False):
        notifications.append("企微机器人")
    
    print(f"🔔 通知方式: {', '.join(notifications) if notifications else '无'}")
    print("=" * 50)
    
    # 启动监控
    monitor = EnhancedOptionMonitor()
    
    try:
        monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n收到停止信号...")
    finally:
        monitor.stop_monitoring()
        print("监控系统已关闭")


if __name__ == '__main__':
    main()