#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
企微机器人通知模块
"""

import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from utils.push_record_manager import PushRecordManager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_option_filter

class WeWorkNotifier:
    """企微机器人通知器"""
    
    def __init__(self, webhook_url: str, mentioned_list: List[str] = None, 
                 mentioned_mobile_list: List[str] = None):
        """
        初始化企微通知器
        
        Args:
            webhook_url: 企微机器人Webhook地址
            mentioned_list: @的用户列表
            mentioned_mobile_list: @的手机号列表
        """
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list or []
        self.mentioned_mobile_list = mentioned_mobile_list or []
        self.logger = logging.getLogger(__name__)
        self.push_record_manager = PushRecordManager()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            message = f"🤖 企微机器人连接测试\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            return self.send_text_message(message)
        except Exception as e:
            self.logger.error(f"企微连接测试失败: {e}")
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
                    self.logger.error(f"企微消息发送失败: {result.get('errmsg')}")
            else:
                self.logger.error(f"企微HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"企微消息发送异常: {e}")
        
        return False
    
    def send_big_option_alert(self, option_data: Dict[str, Any]) -> bool:
        """发送期权大单提醒"""
        try:
            # 生成唯一ID并检查是否已推送
            option_id = self.push_record_manager._generate_option_id(option_data)
            
            if self.push_record_manager.is_pushed(option_id):
                self.logger.info(f"期权大单已推送过，跳过: {option_data.get('option_code')}")
                return True
            
            # 解析期权类型和方向
            option_type = self._parse_option_type(option_data.get('option_code', ''))
            direction = self._parse_direction(option_data.get('trade_direction', ''))
            
            # 获取变化量信息
            volume_diff = option_data.get('volume_diff', 0)
            last_volume = option_data.get('last_volume', 0)
            
            # 格式化变化量显示
            if volume_diff > 0:
                diff_display = f"📈 变化: +{volume_diff} 张 (上次: {last_volume})"
            elif volume_diff < 0:
                diff_display = f"📉 变化: {volume_diff} 张 (上次: {last_volume})"
            else:
                diff_display = f"📊 变化: 无变化 (当前: {option_data.get('volume', 0)})"

            content = f"""🚨 期权大单提醒
📊 股票: {option_data.get('stock_name', 'Unknown')} ({option_data.get('stock_code', 'Unknown')})
🎯 期权: {option_data.get('option_code', 'Unknown')}
📈 类型: {option_type}
🔄 方向: {direction}
💰 价格: {option_data.get('price', 0):.2f} 港币
📦 数量: {option_data.get('volume', 0)} 张
💵 金额: {option_data.get('turnover', 0):,.0f} 港币
{diff_display}
⏰ 时间: {option_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"""
            
            # 发送消息
            result = self.send_text_message(content)
            
            # 标记为已推送
            if result:
                self.push_record_manager.mark_as_pushed(option_id)
                
            return result
            
        except Exception as e:
            self.logger.error(f"发送期权大单提醒失败: {e}")
            return False
    
    def send_summary_report(self, summary_data: Dict[str, Any]) -> tuple:
        """发送汇总报告"""
        try:
            trades = summary_data.get('trades', [])
            timestamp = summary_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            if not trades:
                content = f"📊 期权监控汇总报告\n⏰ 时间: {timestamp}\n📈 状态: 暂无大单交易"
                result = self.send_text_message(content)
                return result, []
            
            # 过滤出新的期权记录
            new_trades = self.push_record_manager.filter_new_options(trades)
            
            # 统计数据
            total_trades = len(trades)
            total_amount = sum(trade.get('turnover', 0) for trade in trades)
            new_trades_count = len(new_trades)
            new_amount = sum(trade.get('turnover', 0) for trade in new_trades)
            
            # 如果没有新的大单，发送简短汇总
            if not new_trades:
                content = f"""📊 期权监控汇总报告
⏰ 时间: {timestamp}
📈 总交易: {total_trades} 笔 (无新增)
💰 总金额: {total_amount:,.0f} 港币"""
                result = self.send_text_message(content)
                return result, []
            
            # 过滤出符合min_volume要求的新增交易
            filtered_new_trades = []
            for trade in new_trades:
                stock_code = trade.get('stock_code', 'Unknown')
                volume_diff = trade.get('volume_diff', 0)
                
                # 获取该股票的配置
                option_filter = get_option_filter(stock_code)
                min_volume = option_filter.get('min_volume', 10)
                
                # 只有增加的交易量>=min_volume才加入通知
                if volume_diff >= min_volume:
                    filtered_new_trades.append(trade)
            
            # 按股票分组 (只统计符合条件的新增交易)
            stock_summary = {}
            for trade in filtered_new_trades:
                stock_code = trade.get('stock_code', 'Unknown')
                stock_name = trade.get('stock_name', 'Unknown')
                if stock_code not in stock_summary:
                    stock_summary[stock_code] = {
                        'name': stock_name,
                        'count': 0,
                        'amount': 0,
                        'trades': []
                    }
                stock_summary[stock_code]['count'] += 1
                stock_summary[stock_code]['amount'] += trade.get('turnover', 0)
                stock_summary[stock_code]['trades'].append(trade)
            
            # 更新统计数据（基于过滤后的交易）
            filtered_trades_count = len(filtered_new_trades)
            filtered_amount = sum(trade.get('turnover', 0) for trade in filtered_new_trades)
            
            # 如果过滤后没有符合条件的交易，发送简短汇总
            if not filtered_new_trades:
                content = f"""📊 期权监控汇总报告
⏰ 时间: {timestamp}
📈 总交易: {total_trades} 笔 (新增: {new_trades_count} 笔，符合通知条件: 0 笔)
💰 总金额: {total_amount:,.0f} 港币 (新增: {new_amount:,.0f} 港币)
📝 说明: 新增交易量未达到通知阈值"""
                # 获取需要标记为已推送的ID，但不立即更新缓存
                option_ids = [trade.get('_id') for trade in new_trades if '_id' in trade]
                
                # 发送消息并返回结果和需要标记的ID
                result = self.send_text_message(content)
                return result, option_ids
            
            content = f"""📊 期权监控汇总报告
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
                top_trades = sorted(info['trades'], 
                                   key=lambda x: x.get('turnover', 0), 
                                   reverse=True)[:3]
                
                for i, trade in enumerate(top_trades, 1):
                    option_type = self._parse_option_type(trade.get('option_code', ''))
                    price = trade.get('price', 0)
                    volume = trade.get('volume', 0)
                    turnover = trade.get('turnover', 0)
                    
                    # 添加买卖方向显示
                    direction = trade.get('direction', 'Unknown')
                    direction_text = ""
                    if direction == "BUY":
                        direction_text = "买入"
                    elif direction == "SELL":
                        direction_text = "卖出"
                    elif direction == "NEUTRAL":
                        direction_text = "中性"
                    
                    direction_display = f", {direction_text}" if direction_text else ""
                    
                    # 添加变化量信息
                    volume_diff = trade.get('volume_diff', 0)
                    if volume_diff > 0:
                        diff_text = f", +{volume_diff}张"
                    elif volume_diff < 0:
                        diff_text = f", {volume_diff}张"
                    else:
                        diff_text = ""
                    
                    content += f"\n  {i}. {trade.get('option_code', '')}: {option_type}{direction_display}, {price:.3f}×{volume}张{diff_text}, {turnover/10000:.1f}万"
            
            # 获取需要标记为已推送的ID，但不立即更新缓存
            option_ids = [trade.get('_id') for trade in new_trades if '_id' in trade]
            
            # 发送消息并返回结果和需要标记的ID
            result = self.send_text_message(content)
            return result, option_ids
            
        except Exception as e:
            self.logger.error(f"发送汇总报告失败: {e}")
            return False
    
    def _parse_option_type(self, option_code: str) -> str:
        """解析期权类型 (Call/Put)"""
        if not option_code:
            return "Unknown"
        
        from utils.option_code_parser import get_option_type
        return get_option_type(option_code)
    
    def _parse_direction(self, trade_direction: str) -> str:
        """解析交易方向"""
        if not trade_direction:
            return "Unknown"
        
        direction_upper = trade_direction.upper()
        if direction_upper in ['BUY', 'B']:
            return "买入 📈"
        elif direction_upper in ['SELL', 'S']:
            return "卖出 📉"
        else:
            return f"{trade_direction} ❓"