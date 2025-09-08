# -*- coding: utf-8 -*-
"""
通知模块
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Union
from datetime import datetime
from config import NOTIFICATION
from utils.mac_notifier import MacNotifier
from utils.wework_notifier import WeWorkNotifier


class Notifier:
    """通知发送器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.Notifier')
        self.mac_notifier = MacNotifier()
        
        # 初始化企业微信通知器
        if isinstance(NOTIFICATION, dict) and NOTIFICATION.get('enable_wework_bot', False):
            wework_config = NOTIFICATION.get('wework_config', {})
            if isinstance(wework_config, dict):
                webhook_url = wework_config.get('webhook_url', '')
                mentioned_list = wework_config.get('mentioned_list', [])
                mentioned_mobile_list = wework_config.get('mentioned_mobile_list', [])
                
                if webhook_url and isinstance(webhook_url, str):
                    self.wework_notifier = WeWorkNotifier(
                        webhook_url=webhook_url,
                        mentioned_list=mentioned_list if isinstance(mentioned_list, list) else [],
                        mentioned_mobile_list=mentioned_mobile_list if isinstance(mentioned_mobile_list, list) else []
                    )
                    self.logger.info("企业微信通知器已初始化")
                else:
                    self.wework_notifier = None
                    self.logger.warning("企业微信webhook URL未配置，企业微信通知功能将被禁用")
            else:
                self.wework_notifier = None
                self.logger.warning("企业微信配置格式错误")
        else:
            self.wework_notifier = None
    
    def send_notification(self, trade_info: Dict[str, Any]):
        """发送交易通知"""
        message = self._format_trade_message(trade_info)
        
        # 控制台通知
        if NOTIFICATION['enable_console']:
            self._send_console_notification(message)
        
        # 邮件通知
        if NOTIFICATION['enable_email']:
            self._send_email_notification(trade_info, message)
        
        # Mac系统通知
        if NOTIFICATION['enable_mac_notification']:
            self._send_mac_notification(trade_info)
            
        # 企业微信通知
        if NOTIFICATION.get('enable_wework_bot', True) and self.wework_notifier:
            self._send_wework_notification(trade_info)
    
    def _format_trade_message(self, trade_info: Dict[str, Any]) -> str:
        """格式化交易信息"""
        # 获取变化量信息
        volume_diff = trade_info.get('volume_diff', 0)
        last_volume = trade_info.get('last_volume', 0)
        
        # 格式化变化量显示
        if volume_diff > 0:
            diff_display = f"变化量: +{volume_diff} 手 (上次: {last_volume})\n"
        elif volume_diff < 0:
            diff_display = f"变化量: {volume_diff} 手 (上次: {last_volume})\n"
        else:
            diff_display = f"变化量: 无变化 (当前: {trade_info.get('volume', 0)})\n"
        
        # 获取股票名称
        stock_name = trade_info.get('stock_name', '')
        stock_display = f"{trade_info['stock_code']} {stock_name}" if stock_name else trade_info['stock_code']
        
        return (
            f"🚨 期权大单交易提醒 🚨\n"
            f"股票: {stock_display}\n"
            f"期权代码: {trade_info['option_code']}\n"
            f"交易时间: {trade_info['time']}\n"
            f"交易价格: {trade_info['price']:.4f}\n"
            f"交易数量: {trade_info['volume']:,}\n"
            f"交易金额: {trade_info['turnover']:,.2f} HKD\n"
            f"交易方向: {trade_info['direction']}\n"
            f"{diff_display}"
            f"发现时间: {trade_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'='*50}"
        )
    
    def _send_console_notification(self, message: str):
        """发送控制台通知"""
        print(f"\n{message}\n")
    
    def _send_email_notification(self, trade_info: Dict[str, Any], message: str):
        """发送邮件通知"""
        try:
            if not isinstance(NOTIFICATION, dict):
                self.logger.warning("通知配置格式错误，跳过邮件通知")
                return
                
            email_config = NOTIFICATION.get('email_config', {})
            if not isinstance(email_config, dict):
                self.logger.warning("邮件配置格式错误，跳过邮件通知")
                return
            
            username = email_config.get('username', '')
            to_emails = email_config.get('to_emails', [])
            
            if not username or not to_emails or not isinstance(to_emails, list):
                self.logger.warning("邮件配置不完整，跳过邮件通知")
                return
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = str(username)
            msg['To'] = ', '.join(str(email) for email in to_emails)
            msg['Subject'] = f"期权大单提醒 - {trade_info.get('stock_code', 'Unknown')}"
            
            # 添加邮件正文
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # 发送邮件
            smtp_server = email_config.get('smtp_server', '')
            smtp_port = email_config.get('smtp_port', 587)
            password = email_config.get('password', '')
            
            if not smtp_server or not password:
                self.logger.warning("SMTP配置不完整，跳过邮件通知")
                return
            
            # 确保 smtp_port 是整数
            try:
                port = int(smtp_port) if isinstance(smtp_port, (str, int)) else 587
            except (ValueError, TypeError):
                port = 587
                self.logger.warning(f"SMTP端口格式错误，使用默认端口587")
            
            with smtplib.SMTP(str(smtp_server), port) as server:
                server.starttls()
                server.login(str(username), str(password))
                server.send_message(msg)
            
            self.logger.info(f"邮件通知已发送: {trade_info.get('option_code', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"发送邮件通知失败: {e}")
    
    def _send_mac_notification(self, trade_info: Dict[str, Any]):
        """发送Mac系统通知"""
        try:
            # 获取股票名称
            stock_name = trade_info.get('stock_name', '')
            stock_display = f"{trade_info['stock_code']} {stock_name}" if stock_name else trade_info['stock_code']
            
            title = f"期权大单 - {stock_display}"
            subtitle = f"{trade_info['option_code']}"
            message = (f"成交量: {trade_info['volume']:,}手\n"
                      f"成交额: {trade_info['turnover']/10000:.1f}万港币")
            
            self.mac_notifier.send_notification(title, message, subtitle)
            
        except Exception as e:
            self.logger.error(f"发送Mac通知失败: {e}")

    def _send_wework_notification(self, trade_info: Dict[str, Any]):
        """发送企业微信通知"""
        try:
            if not self.wework_notifier:
                return
                
            # 添加股票名称
            stock_name = self._get_stock_name(trade_info['stock_code'])
            trade_info['stock_name'] = stock_name
            
            # 发送企业微信通知
            self.wework_notifier.send_big_option_alert(trade_info)
            self.logger.debug(f"企业微信通知已发送: {trade_info['option_code']}")
            
        except Exception as e:
            self.logger.error(f"发送企业微信通知失败: {e}")
    
    def _get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        stock_names = {
            'HK.00700': '腾讯控股',
            'HK.09988': '阿里巴巴',
            'HK.03690': '美团',
            'HK.01810': '小米集团',
            'HK.09618': '京东集团',
            'HK.02318': '中国平安',
            'HK.00388': '香港交易所',
        }
        return stock_names.get(stock_code, stock_code)
    
    def send_big_options_summary(self, big_options: List[Dict[str, Any]]):
        """发送大单期权汇总"""
        try:
            if not big_options:
                self.logger.info("没有大单期权，跳过汇总通知")
                return
                
            # 准备汇总数据
            summary_data = {
                'trades': big_options,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 发送企业微信汇总通知
            if NOTIFICATION.get('enable_wework_bot', True) and self.wework_notifier:
                self.wework_notifier.send_summary_report(summary_data)
                self.logger.info(f"企业微信汇总通知已发送: {len(big_options)}笔交易")
                
        except Exception as e:
            self.logger.error(f"发送大单期权汇总失败: {e}")