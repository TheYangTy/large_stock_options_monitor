# -*- coding: utf-8 -*-
"""
Mac系统通知模块
"""

import subprocess
import logging
import platform
from typing import Dict, List


class MacNotifier:
    """Mac系统通知器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.MacNotifier')
        self.is_mac = platform.system() == 'Darwin'
        
        if not self.is_mac:
            self.logger.warning("当前系统不是macOS，Mac通知功能将被禁用")
    
    def send_notification(self, title: str, message: str, subtitle: str = ""):
        """发送Mac系统通知"""
        if not self.is_mac:
            self.logger.debug("非Mac系统，跳过系统通知")
            return False
        
        try:
            # 构建osascript命令
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            
            if subtitle:
                script = f'''
                display notification "{message}" with title "{title}" subtitle "{subtitle}"
                '''
            
            # 执行AppleScript
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.logger.info(f"Mac通知发送成功: {title}")
                return True
            else:
                self.logger.error(f"Mac通知发送失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Mac通知发送超时")
            return False
        except Exception as e:
            self.logger.error(f"Mac通知发送异常: {e}")
            return False
    
    def send_big_options_summary(self, big_options: List[Dict]):
        """发送大单期权汇总通知"""
        if not big_options:
            return
        
        total_count = len(big_options)
        total_turnover = sum(opt.get('turnover', 0) for opt in big_options)
        
        # 按股票分组统计
        stock_stats = {}
        for opt in big_options:
            stock_code = opt.get('stock_code', 'Unknown')
            if stock_code not in stock_stats:
                stock_stats[stock_code] = {'count': 0, 'turnover': 0}
            stock_stats[stock_code]['count'] += 1
            stock_stats[stock_code]['turnover'] += opt.get('turnover', 0)
        
        # 构建通知消息
        title = "🚨 港股期权大单提醒"
        subtitle = f"发现 {total_count} 笔大单交易"
        
        # 构建详细消息
        message_parts = [
            f"总交易数: {total_count}",
            f"总金额: {total_turnover/10000:.1f}万港币"
        ]
        
        # 添加前3个股票的统计
        top_stocks = sorted(stock_stats.items(), 
                          key=lambda x: x[1]['turnover'], 
                          reverse=True)[:3]
        
        if top_stocks:
            message_parts.append("主要股票:")
            for stock, stats in top_stocks:
                message_parts.append(f"  {stock}: {stats['count']}笔")
        
        message = "\n".join(message_parts)
        
        self.send_notification(title, message, subtitle)