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
        if NOTIFICATION.get('enable_wework_bot', False) and self.wework_notifier:
            self._send_wework_notification(trade_info)
    
    def _format_trade_message(self, trade_info: Dict[str, Any]) -> str:
        """格式化交易信息（时间兼容格式化 + 展示期权类型）"""
        # 获取变化量信息
        volume_diff = trade_info.get('volume_diff', 0)
        last_volume = trade_info.get('last_volume', 0)

        # 格式化变化量显示
        if volume_diff > 0:
            diff_display = f"变化量: +{volume_diff} 张 (上次: {last_volume})\n"
        elif volume_diff < 0:
            diff_display = f"变化量: {volume_diff} 张 (上次: {last_volume})\n"
        else:
            diff_display = f"变化量: 无变化 (当前: {trade_info.get('volume', 0)})\n"

        # 获取股票名称
        stock_name = trade_info.get('stock_name', '')
        stock_display = f"{trade_info['stock_code']} {stock_name}" if stock_name else trade_info['stock_code']

        # 使用原始方向字符串，不做中文映射
        direction_display = str(trade_info.get('direction', 'Unknown') or 'Unknown')

        # 发现时间格式化（兼容 datetime 或 ISO 字符串）
        ts_obj = trade_info.get('timestamp')
        ts_text = ''
        try:
            if hasattr(ts_obj, 'strftime'):
                ts_text = ts_obj.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(ts_obj, str):
                try:
                    ts_text = datetime.fromisoformat(ts_obj).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    ts_text = ts_obj
            else:
                ts_text = ''
        except Exception:
            ts_text = ''

        # 可选：解析期权类型（Call/Put），用于增强文案（不影响现有格式）
        opt_type_text = ''
        try:
            code = trade_info.get('option_code', '')
            if isinstance(code, str) and code.startswith('HK.'):
                code_part = code[3:]
                import re as _re
                m = _re.search(r'\d+([CP])\d+', code_part)
                if m:
                    opt_type_text = 'Call' if m.group(1) == 'C' else 'Put'
        except Exception:
            opt_type_text = ''

        return (
            f"🚨 期权大单交易提醒 🚨\n"
            f"股票: {stock_display}\n"
            f"期权代码: {trade_info.get('option_code', 'Unknown')}{(' | ' + opt_type_text) if opt_type_text else ''}\n"
            f"交易时间: {trade_info.get('time', '')}\n"
            f"交易价格: {float(trade_info.get('price', 0)):.4f}\n"
            f"交易数量: {int(trade_info.get('volume', 0)):,}\n"
            f"交易金额: {float(trade_info.get('turnover', 0)):,.2f} HKD\n"
            f"交易方向: {direction_display}\n"
            f"{diff_display}"
            f"发现时间: {ts_text}\n"
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
            message = (f"成交量: {trade_info['volume']:,}张\n"
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

            # 解析期权类型并带入trade_info，兼容模板字段(tx)
            try:
                code = trade_info.get('option_code', '')
                opt_type = ''
                opt_type_text = ''
                if isinstance(code, str) and code.startswith('HK.'):
                    code_part = code[3:]
                    import re as _re
                    m = _re.search(r'\d+([CP])\d+', code_part)
                    if m:
                        opt_type = 'Call' if m.group(1) == 'C' else 'Put'
                        opt_type_text = 'Call' if opt_type == 'Call' else 'Put'
                # 写入期权类型字段
                if opt_type:
                    trade_info['option_type'] = opt_type
                    trade_info['option_type_text'] = opt_type_text
                    # 兼容模板使用的 tx 字段
                    trade_info.setdefault('tx', opt_type)
            except Exception:
                pass

            # 发送企业微信通知（主 webhook）
            ok_main = self.wework_notifier.send_big_option_alert(trade_info)
            self.logger.debug(f"企业微信通知已发送: {trade_info['option_code']} (主webhook: {bool(ok_main)})")

            # 兼容额外 webhook 列表
            try:
                from config import NOTIFICATION as _NOTIF_
                wework_cfg = _NOTIF_.get('wework_config', {}) if isinstance(_NOTIF_, dict) else {}
                extra_urls = wework_cfg.get('extra_webhook_urls', [])
                if isinstance(extra_urls, str):
                    extra_urls = [extra_urls] if extra_urls.strip() else []
                if isinstance(extra_urls, list) and extra_urls:
                    for url in extra_urls:
                        try:
                            if not url or not isinstance(url, str):
                                continue
                            extra_notifier = WeWorkNotifier(
                                webhook_url=url.strip(),
                                mentioned_list=wework_cfg.get('mentioned_list', []),
                                mentioned_mobile_list=wework_cfg.get('mentioned_mobile_list', [])
                            )
                            ok = extra_notifier.send_big_option_alert(trade_info)
                            self.logger.debug(f"企业微信通知已发送(额外): {trade_info['option_code']} -> {url[:40]}... (ok={bool(ok)})")
                        except Exception as _e:
                            self.logger.warning(f"额外webhook发送失败: {url}, err={_e}")
            except Exception as _e2:
                self.logger.warning(f"处理额外webhook发生异常: {_e2}")
            
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
            
            # 发送企业微信汇总通知（主 webhook）
            if NOTIFICATION.get('enable_wework_bot', False) and self.wework_notifier:
                # 收集所有需要标记为已推送的记录ID
                all_option_ids = []
                
                # 主webhook推送
                result_main, option_ids_main = self.wework_notifier.send_summary_report(summary_data)
                if option_ids_main:
                    all_option_ids.extend(option_ids_main)
                self.logger.info(f"企业微信汇总通知已发送(主webhook): {len(big_options)}笔交易, ok={bool(result_main)}")

                # 额外 webhook 并行发送
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
                                extra_notifier = WeWorkNotifier(
                                    webhook_url=url.strip(),
                                    mentioned_list=wework_cfg.get('mentioned_list', []),
                                    mentioned_mobile_list=wework_cfg.get('mentioned_mobile_list', [])
                                )
                                result, option_ids = extra_notifier.send_summary_report(summary_data)
                                # 不需要收集额外的option_ids，因为它们与主webhook的相同
                                self.logger.info(f"企业微信汇总通知已发送(额外): ok={bool(result)} url={url[:40]}...")
                            except Exception as _e:
                                self.logger.warning(f"额外webhook汇总发送失败: {url}, err={_e}")
                except Exception as _e2:
                    self.logger.warning(f"处理额外webhook(汇总)发生异常: {_e2}")
                
                # 所有webhook推送完成后，统一更新缓存
                if all_option_ids:
                    try:
                        self.wework_notifier.push_record_manager.mark_batch_as_pushed(all_option_ids)
                        self.logger.info(f"已更新推送记录缓存，标记{len(all_option_ids)}条记录为已推送")
                    except Exception as e:
                        self.logger.error(f"更新推送记录缓存失败: {e}")
                
        except Exception as e:
            self.logger.error(f"发送大单期权汇总失败: {e}")