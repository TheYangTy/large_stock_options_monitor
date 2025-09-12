# -*- coding: utf-8 -*-
"""
V2通知管理器 - 复用V1通知逻辑但保持代码独立
"""

import smtplib
import logging
import subprocess
import platform
import requests
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Union, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from config import NOTIFICATION, get_option_filter


@dataclass
class NotificationData:
    """通知数据结构"""
    stock_code: str
    stock_name: str
    option_code: str
    option_type: str
    strike_price: float
    expiry_date: str
    price: float
    volume: int
    turnover: float
    direction: str
    timestamp: datetime
    volume_diff: int = 0
    last_volume: int = 0
    risk_level: str = ""
    importance_score: int = 0
    moneyness: str = ""
    days_to_expiry: int = 0


class V2PushRecordManager:
    """V2推送记录管理器"""
    
    def __init__(self, record_file: str = 'data/v2_pushed_options.json'):
        self.logger = logging.getLogger('OptionMonitorV2.PushRecordManager')
        self.record_file = record_file
        self.pushed_records = set()
        self.last_load_time = None
        
        # 确保目录存在
        os.makedirs(os.path.dirname(record_file), exist_ok=True)
        self._load_records()
    
    def _load_records(self):
        """加载已推送记录"""
        try:
            if os.path.exists(self.record_file):
                with open(self.record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pushed_records = set(data.get('pushed_ids', []))
                    self.logger.info(f"V2已加载 {len(self.pushed_records)} 条推送记录")
            else:
                self.pushed_records = set()
            
            self.last_load_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"V2加载推送记录失败: {e}")
            self.pushed_records = set()
            self.last_load_time = datetime.now()
    
    def _save_records(self):
        """保存已推送记录"""
        try:
            data = {
                'update_time': datetime.now().isoformat(),
                'pushed_ids': list(self.pushed_records),
                'count': len(self.pushed_records),
                'version': 'v2'
            }
            
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"V2已保存 {len(self.pushed_records)} 条推送记录")
            
        except Exception as e:
            self.logger.error(f"V2保存推送记录失败: {e}")
    
    def is_pushed(self, option_id: str) -> bool:
        """检查期权是否已推送"""
        if self.last_load_time and (datetime.now() - self.last_load_time).seconds > 600:
            self._load_records()
        
        return option_id in self.pushed_records
    
    def mark_as_pushed(self, option_id: str):
        """标记期权为已推送"""
        self.pushed_records.add(option_id)
        self._save_records()
    
    def mark_batch_as_pushed(self, option_ids: List[str]):
        """批量标记期权为已推送"""
        self.pushed_records.update(option_ids)
        self._save_records()
    
    def generate_option_id(self, notification_data: NotificationData) -> str:
        """生成期权记录的唯一ID"""
        timestamp_str = notification_data.timestamp.isoformat()
        option_id = f"{notification_data.option_code}_{notification_data.volume}_{int(notification_data.turnover)}_{timestamp_str}"
        return option_id
    
    def filter_new_notifications(self, notifications: List[NotificationData]) -> List[NotificationData]:
        """过滤出新的通知记录"""
        new_notifications = []
        
        for notification in notifications:
            option_id = self.generate_option_id(notification)
            
            if not self.is_pushed(option_id):
                new_notifications.append(notification)
        
        return new_notifications


class V2MacNotifier:
    """V2 Mac系统通知器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitorV2.MacNotifier')
        self.is_mac = platform.system() == 'Darwin'
        
        if not self.is_mac:
            self.logger.warning("当前系统不是macOS，Mac通知功能将被禁用")
    
    def send_notification(self, title: str, message: str, subtitle: str = ""):
        """发送Mac系统通知"""
        if not self.is_mac:
            self.logger.debug("非Mac系统，跳过系统通知")
            return False
        
        try:
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            
            if subtitle:
                script = f'''
                display notification "{message}" with title "{title}" subtitle "{subtitle}"
                '''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.logger.info(f"V2 Mac通知发送成功: {title}")
                return True
            else:
                self.logger.error(f"V2 Mac通知发送失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("V2 Mac通知发送超时")
            return False
        except Exception as e:
            self.logger.error(f"V2 Mac通知发送异常: {e}")
            return False
    
    def send_big_trade_notification(self, notification_data: NotificationData):
        """发送大单交易通知"""
        try:
            stock_display = f"{notification_data.stock_code} {notification_data.stock_name}" if notification_data.stock_name else notification_data.stock_code
            
            title = f"期权大单 - {stock_display}"
            subtitle = f"{notification_data.option_code}"
            message = (f"成交量: {notification_data.volume:,}张\n"
                      f"成交额: {notification_data.turnover/10000:.1f}万港币")
            
            return self.send_notification(title, message, subtitle)
            
        except Exception as e:
            self.logger.error(f"V2发送Mac大单通知失败: {e}")
            return False


class V2WeWorkNotifier:
    """V2企业微信通知器"""
    
    def __init__(self, webhook_url: str, mentioned_list: List[str] = None, 
                 mentioned_mobile_list: List[str] = None):
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list or []
        self.mentioned_mobile_list = mentioned_mobile_list or []
        self.logger = logging.getLogger('OptionMonitorV2.WeWorkNotifier')
        self.push_record_manager = V2PushRecordManager()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            message = f"🤖 V2企微机器人连接测试\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            return self.send_text_message(message)
        except Exception as e:
            self.logger.error(f"V2企微连接测试失败: {e}")
            return False
    
    def send_text_message(self, content: str) -> bool:
        """发送文本消息"""
        try:
            data = {
                "msgtype": "text",
                "text": {
                    "content": content,
                    "mentioned_list": self.mentioned_list,
                    "mentioned_mobile_list": self.mentioned_mobile_list
                }
            }
            
            response = requests.post(self.webhook_url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return True
                else:
                    self.logger.error(f"V2企微消息发送失败: {result.get('errmsg')}")
            else:
                self.logger.error(f"V2企微HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"V2企微消息发送异常: {e}")
        
        return False
    
    def send_big_trade_alert(self, notification_data: NotificationData) -> bool:
        """发送期权大单提醒"""
        try:
            # 生成唯一ID并检查是否已推送
            option_id = self.push_record_manager.generate_option_id(notification_data)
            
            if self.push_record_manager.is_pushed(option_id):
                self.logger.info(f"V2期权大单已推送过，跳过: {notification_data.option_code}")
                return True
            
            # 解析期权类型和方向
            option_type = self._parse_option_type(notification_data.option_type)
            direction = self._parse_direction(notification_data.direction)
            
            # 格式化变化量显示
            if notification_data.volume_diff > 0:
                diff_display = f"📈 变化: +{notification_data.volume_diff} 张 (上次: {notification_data.last_volume})"
            elif notification_data.volume_diff < 0:
                diff_display = f"📉 变化: {notification_data.volume_diff} 张 (上次: {notification_data.last_volume})"
            else:
                diff_display = f"📊 变化: 无变化 (当前: {notification_data.volume})"

            content = f"""🚨 V2期权大单提醒
📊 股票: {notification_data.stock_name} ({notification_data.stock_code})
🎯 期权: {notification_data.option_code}
📈 类型: {option_type}
🔄 方向: {direction}
💰 价格: {notification_data.price:.2f} 港币
📦 数量: {notification_data.volume} 张
💵 金额: {notification_data.turnover:,.0f} 港币
{diff_display}
🎯 重要性: {notification_data.importance_score}/100
⚠️ 风险: {notification_data.risk_level}
📊 状态: {notification_data.moneyness}
📅 到期: {notification_data.days_to_expiry}天
⏰ 时间: {notification_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""
            
            # 发送消息
            result = self.send_text_message(content)
            
            # 标记为已推送
            if result:
                self.push_record_manager.mark_as_pushed(option_id)
                
            return result
            
        except Exception as e:
            self.logger.error(f"V2发送期权大单提醒失败: {e}")
            return False
    
    def send_summary_report(self, notifications: List[NotificationData]) -> tuple:
        """发送汇总报告"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if not notifications:
                content = f"📊 V2期权监控汇总报告\n⏰ 时间: {timestamp}\n📈 状态: 暂无大单交易"
                result = self.send_text_message(content)
                return result, []
            
            # 过滤出新的期权记录
            new_notifications = self.push_record_manager.filter_new_notifications(notifications)
            
            # 统计数据
            total_trades = len(notifications)
            total_amount = sum(n.turnover for n in notifications)
            new_trades_count = len(new_notifications)
            new_amount = sum(n.turnover for n in new_notifications)
            
            # 如果没有新的大单，发送简短汇总
            if not new_notifications:
                content = f"""📊 V2期权监控汇总报告
⏰ 时间: {timestamp}
📈 总交易: {total_trades} 笔 (无新增)
💰 总金额: {total_amount:,.0f} 港币"""
                result = self.send_text_message(content)
                return result, []
            
            # 过滤出符合min_volume要求的新增交易
            filtered_notifications = []
            for notification in new_notifications:
                option_filter = get_option_filter(notification.stock_code)
                min_volume = option_filter.get('min_volume', 10)
                
                # 只有增加的交易量>=min_volume才加入通知
                if notification.volume_diff >= min_volume:
                    filtered_notifications.append(notification)
            
            # 按股票分组
            stock_summary = {}
            for notification in filtered_notifications:
                stock_code = notification.stock_code
                if stock_code not in stock_summary:
                    stock_summary[stock_code] = {
                        'name': notification.stock_name,
                        'count': 0,
                        'amount': 0,
                        'notifications': []
                    }
                stock_summary[stock_code]['count'] += 1
                stock_summary[stock_code]['amount'] += notification.turnover
                stock_summary[stock_code]['notifications'].append(notification)
            
            # 更新统计数据
            filtered_trades_count = len(filtered_notifications)
            filtered_amount = sum(n.turnover for n in filtered_notifications)
            
            # 如果过滤后没有符合条件的交易
            if not filtered_notifications:
                content = f"""📊 V2期权监控汇总报告
⏰ 时间: {timestamp}
📈 总交易: {total_trades} 笔 (新增: {new_trades_count} 笔，符合通知条件: 0 笔)
💰 总金额: {total_amount:,.0f} 港币 (新增: {new_amount:,.0f} 港币)
📝 说明: 新增交易量未达到通知阈值"""
                
                # 获取需要标记为已推送的ID
                option_ids = [self.push_record_manager.generate_option_id(n) for n in new_notifications]
                
                result = self.send_text_message(content)
                return result, option_ids
            
            content = f"""📊 V2期权监控汇总报告
⏰ 时间: {timestamp}
📈 总交易: {total_trades} 笔 (新增: {new_trades_count} 笔，符合通知条件: {filtered_trades_count} 笔)
💰 总金额: {total_amount:,.0f} 港币 (新增: {new_amount:,.0f} 港币，符合条件: {filtered_amount:,.0f} 港币)

📋 新增大单统计:"""
            
            # 按成交额排序
            sorted_stocks = sorted(stock_summary.items(), 
                                  key=lambda x: x[1]['amount'], 
                                  reverse=True)
            
            for stock_code, info in sorted_stocks:
                content += f"\n• {info['name']} ({stock_code}): {info['count']}笔, {info['amount']:,.0f}港币"
                
                # 添加该股票的前3笔最大交易详情
                top_notifications = sorted(info['notifications'], 
                                         key=lambda x: x.turnover, 
                                         reverse=True)[:3]
                
                for i, notification in enumerate(top_notifications, 1):
                    option_type = self._parse_option_type(notification.option_type)
                    
                    # 添加买卖方向显示
                    direction_text = ""
                    if notification.direction == "BUY":
                        direction_text = "买入"
                    elif notification.direction == "SELL":
                        direction_text = "卖出"
                    elif notification.direction == "NEUTRAL":
                        direction_text = "中性"
                    
                    direction_display = f", {direction_text}" if direction_text else ""
                    
                    # 添加变化量信息
                    if notification.volume_diff > 0:
                        diff_text = f", +{notification.volume_diff}张"
                    elif notification.volume_diff < 0:
                        diff_text = f", {notification.volume_diff}张"
                    else:
                        diff_text = ""
                    
                    content += f"\n  {i}. {notification.option_code}: {option_type}{direction_display}, {notification.price:.3f}×{notification.volume}张{diff_text}, {notification.turnover/10000:.1f}万"
            
            # 获取需要标记为已推送的ID
            option_ids = [self.push_record_manager.generate_option_id(n) for n in new_notifications]
            
            result = self.send_text_message(content)
            return result, option_ids
            
        except Exception as e:
            self.logger.error(f"V2发送汇总报告失败: {e}")
            return False, []
    
    def _parse_option_type(self, option_type: str) -> str:
        """解析期权类型"""
        if option_type == "Call":
            return "Call"
        elif option_type == "Put":
            return "Put"
        else:
            return "Unknown"
    
    def _parse_direction(self, direction: str) -> str:
        """解析交易方向"""
        if not direction:
            return "Unknown"
        
        direction_upper = direction.upper()
        if direction_upper in ['BUY', 'B']:
            return "买入 📈"
        elif direction_upper in ['SELL', 'S']:
            return "卖出 📉"
        else:
            return f"{direction} ❓"


class V2NotificationManager:
    """V2通知管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitorV2.NotificationManager')
        
        # 初始化Mac通知器
        self.mac_notifier = V2MacNotifier()
        
        # 初始化企业微信通知器
        self.wework_notifier = None
        self._init_wework_notifier()
        
        # 股票名称映射
        self.stock_names = {
            'HK.00700': '腾讯控股',
            'HK.09988': '阿里巴巴',
            'HK.03690': '美团',
            'HK.01810': '小米集团',
            'HK.09618': '京东集团',
            'HK.02318': '中国平安',
            'HK.00388': '香港交易所',
        }
    
    def _init_wework_notifier(self):
        """初始化企业微信通知器"""
        try:
            if isinstance(NOTIFICATION, dict) and NOTIFICATION.get('enable_wework_bot', False):
                wework_config = NOTIFICATION.get('wework_config', {})
                if isinstance(wework_config, dict):
                    webhook_url = wework_config.get('webhook_url', '')
                    mentioned_list = wework_config.get('mentioned_list', [])
                    mentioned_mobile_list = wework_config.get('mentioned_mobile_list', [])
                    
                    if webhook_url and isinstance(webhook_url, str):
                        self.wework_notifier = V2WeWorkNotifier(
                            webhook_url=webhook_url,
                            mentioned_list=mentioned_list if isinstance(mentioned_list, list) else [],
                            mentioned_mobile_list=mentioned_mobile_list if isinstance(mentioned_mobile_list, list) else []
                        )
                        self.logger.info("V2企业微信通知器已初始化")
                    else:
                        self.logger.warning("V2企业微信webhook URL未配置")
                else:
                    self.logger.warning("V2企业微信配置格式错误")
        except Exception as e:
            self.logger.error(f"V2初始化企业微信通知器失败: {e}")
    
    def send_big_trade_notification(self, notification_data: NotificationData):
        """发送大单交易通知"""
        try:
            # 补充股票名称
            if not notification_data.stock_name:
                notification_data.stock_name = self.stock_names.get(notification_data.stock_code, notification_data.stock_code)
            
            # 控制台通知
            if NOTIFICATION.get('enable_console', True):
                self._send_console_notification(notification_data)
            
            # 邮件通知
            if NOTIFICATION.get('enable_email', False):
                self._send_email_notification(notification_data)
            
            # Mac系统通知
            if NOTIFICATION.get('enable_mac_notification', False):
                self.mac_notifier.send_big_trade_notification(notification_data)
            
            # 企业微信通知
            if NOTIFICATION.get('enable_wework_bot', False) and self.wework_notifier:
                self.wework_notifier.send_big_trade_alert(notification_data)
                
                # 处理额外的webhook
                self._send_extra_wework_notifications(notification_data)
            
        except Exception as e:
            self.logger.error(f"V2发送大单交易通知失败: {e}")
    
    def send_summary_notification(self, notifications: List[NotificationData]):
        """发送汇总通知"""
        try:
            if not notifications:
                self.logger.info("V2没有大单期权，跳过汇总通知")
                return
            
            # 发送企业微信汇总通知
            if NOTIFICATION.get('enable_wework_bot', False) and self.wework_notifier:
                # 收集所有需要标记为已推送的记录ID
                all_option_ids = []
                
                # 主webhook推送
                result_main, option_ids_main = self.wework_notifier.send_summary_report(notifications)
                if option_ids_main:
                    all_option_ids.extend(option_ids_main)
                self.logger.info(f"V2企业微信汇总通知已发送(主webhook): {len(notifications)}笔交易, ok={bool(result_main)}")

                # 额外webhook推送
                self._send_extra_wework_summary(notifications)
                
                # 统一更新缓存
                if all_option_ids:
                    try:
                        self.wework_notifier.push_record_manager.mark_batch_as_pushed(all_option_ids)
                        self.logger.info(f"V2已更新推送记录缓存，标记{len(all_option_ids)}条记录为已推送")
                    except Exception as e:
                        self.logger.error(f"V2更新推送记录缓存失败: {e}")
                
        except Exception as e:
            self.logger.error(f"V2发送汇总通知失败: {e}")
    
    def _send_console_notification(self, notification_data: NotificationData):
        """发送控制台通知"""
        try:
            # 格式化变化量显示
            if notification_data.volume_diff > 0:
                diff_display = f"变化量: +{notification_data.volume_diff} 张 (上次: {notification_data.last_volume})\n"
            elif notification_data.volume_diff < 0:
                diff_display = f"变化量: {notification_data.volume_diff} 张 (上次: {notification_data.last_volume})\n"
            else:
                diff_display = f"变化量: 无变化 (当前: {notification_data.volume})\n"

            stock_display = f"{notification_data.stock_code} {notification_data.stock_name}" if notification_data.stock_name else notification_data.stock_code

            message = (
                f"🚨 V2期权大单交易提醒 🚨\n"
                f"股票: {stock_display}\n"
                f"期权代码: {notification_data.option_code} | {notification_data.option_type}\n"
                f"交易时间: {notification_data.timestamp.strftime('%H:%M:%S')}\n"
                f"交易价格: {notification_data.price:.4f}\n"
                f"交易数量: {notification_data.volume:,}\n"
                f"交易金额: {notification_data.turnover:,.2f} HKD\n"
                f"交易方向: {notification_data.direction}\n"
                f"{diff_display}"
                f"重要性分数: {notification_data.importance_score}/100\n"
                f"风险等级: {notification_data.risk_level}\n"
                f"发现时间: {notification_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*50}"
            )
            
            print(f"\n{message}\n")
            
        except Exception as e:
            self.logger.error(f"V2发送控制台通知失败: {e}")
    
    def _send_email_notification(self, notification_data: NotificationData):
        """发送邮件通知"""
        try:
            if not isinstance(NOTIFICATION, dict):
                return
                
            email_config = NOTIFICATION.get('email_config', {})
            if not isinstance(email_config, dict):
                return
            
            username = email_config.get('username', '')
            to_emails = email_config.get('to_emails', [])
            
            if not username or not to_emails or not isinstance(to_emails, list):
                return
            
            # 创建邮件内容
            message = self._format_email_message(notification_data)
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = str(username)
            msg['To'] = ', '.join(str(email) for email in to_emails)
            msg['Subject'] = f"V2期权大单提醒 - {notification_data.stock_code}"
            
            # 添加邮件正文
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # 发送邮件
            smtp_server = email_config.get('smtp_server', '')
            smtp_port = email_config.get('smtp_port', 587)
            password = email_config.get('password', '')
            
            if not smtp_server or not password:
                return
            
            try:
                port = int(smtp_port) if isinstance(smtp_port, (str, int)) else 587
            except (ValueError, TypeError):
                port = 587
            
            with smtplib.SMTP(str(smtp_server), port) as server:
                server.starttls()
                server.login(str(username), str(password))
                server.send_message(msg)
            
            self.logger.info(f"V2邮件通知已发送: {notification_data.option_code}")
            
        except Exception as e:
            self.logger.error(f"V2发送邮件通知失败: {e}")
    
    def _format_email_message(self, notification_data: NotificationData) -> str:
        """格式化邮件消息"""
        return f"""V2期权大单交易提醒

股票信息:
- 股票代码: {notification_data.stock_code}
- 股票名称: {notification_data.stock_name}

期权信息:
- 期权代码: {notification_data.option_code}
- 期权类型: {notification_data.option_type}
- 执行价格: {notification_data.strike_price}
- 到期日期: {notification_data.expiry_date}
- 到期天数: {notification_data.days_to_expiry}

交易信息:
- 交易价格: {notification_data.price:.4f} 港币
- 交易数量: {notification_data.volume:,} 张
- 交易金额: {notification_data.turnover:,.2f} 港币
- 交易方向: {notification_data.direction}
- 交易时间: {notification_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

分析信息:
- 价值状态: {notification_data.moneyness}
- 风险等级: {notification_data.risk_level}
- 重要性分数: {notification_data.importance_score}/100
- 交易量变化: {notification_data.volume_diff} 张 (上次: {notification_data.last_volume})

此邮件由V2港股期权大单监控系统自动发送。
"""
    
    def _send_extra_wework_notifications(self, notification_data: NotificationData):
        """发送额外的企业微信通知"""
        try:
            wework_cfg = NOTIFICATION.get('wework_config', {}) if isinstance(NOTIFICATION, dict) else {}
            extra_urls = wework_cfg.get('extra_webhook_urls', [])
            
            if isinstance(extra_urls, str):
                extra_urls = [extra_urls] if extra_urls.strip() else []
                
            if isinstance(extra_urls, list) and extra_urls:
                for url in extra_urls:
                    try:
                        if not url or not isinstance(url, str):
                            continue
                            
                        extra_notifier = V2WeWorkNotifier(
                            webhook_url=url.strip(),
                            mentioned_list=wework_cfg.get('mentioned_list', []),
                            mentioned_mobile_list=wework_cfg.get('mentioned_mobile_list', [])
                        )
                        
                        ok = extra_notifier.send_big_trade_alert(notification_data)
                        self.logger.debug(f"V2企业微信通知已发送(额外): {notification_data.option_code} -> {url[:40]}... (ok={bool(ok)})")
                        
                    except Exception as e:
                        self.logger.warning(f"V2额外webhook发送失败: {url}, err={e}")
                        
        except Exception as e:
            self.logger.warning(f"V2处理额外webhook发生异常: {e}")
    
    def _send_extra_wework_summary(self, notifications: List[NotificationData]):
        """发送额外的企业微信汇总通知"""
        try:
            wework_cfg = NOTIFICATION.get('wework_config', {}) if isinstance(NOTIFICATION, dict) else {}
            extra_urls = wework_cfg.get('extra_webhook_urls', [])
            
            if isinstance(extra_urls, str):
                extra_urls = [extra_urls] if extra_urls.strip() else []
                
            if isinstance(extra_urls, list) and extra_urls:
                for url in extra_urls:
                    try:
                        if not url or not isinstance(url, str):
                            continue
                            
                        extra_notifier = V2WeWorkNotifier(
                            webhook_url=url.strip(),
                            mentioned_list=wework_cfg.get('mentioned_list', []),
                            mentioned_mobile_list=wework_cfg.get('mentioned_mobile_list', [])
                        )
                        
                        result, option_ids = extra_notifier.send_summary_report(notifications)
                        self.logger.info(f"V2企业微信汇总通知已发送(额外): ok={bool(result)} url={url[:40]}...")
                        
                    except Exception as e:
                        self.logger.warning(f"V2额外webhook汇总发送失败: {url}, err={e}")
                        
        except Exception as e:
            self.logger.warning(f"V2处理额外webhook(汇总)发生异常: {e}")