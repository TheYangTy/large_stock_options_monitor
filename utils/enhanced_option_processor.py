#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版期权数据处理器
包含Call/Put识别和买卖方向分析
"""

import json
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from config import OPTION_FILTER, DATA_CONFIG

class EnhancedOptionProcessor:
    """增强版期权数据处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.logger = logging.getLogger(__name__)
        self.last_alerts = {}  # 记录最近的提醒，避免重复
    
    def enhance_option_data(self, option_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强期权数据"""
        try:
            enhanced_data = option_data.copy()
            
            # 解析期权类型
            enhanced_data['option_type'] = self._parse_option_type(
                option_data.get('option_code', '')
            )
            
            # 解析交易方向
            enhanced_data['direction'] = self._parse_trade_direction(
                option_data.get('trade_direction', '')
            )
            
            # 计算成交额
            volume = option_data.get('volume', 0)
            price = option_data.get('price', 0)
            enhanced_data['turnover'] = volume * price * 100  # 港股期权合约乘数通常是100
            
            # 添加风险等级
            enhanced_data['risk_level'] = self._calculate_risk_level(enhanced_data)
            
            # 添加重要性评分
            enhanced_data['importance_score'] = self._calculate_importance_score(enhanced_data)
            
            return enhanced_data
            
        except Exception as e:
            self.logger.error(f"增强期权数据失败: {e}")
            return option_data
    
    def should_notify(self, option_data: Dict[str, Any]) -> bool:
        """判断是否需要发送通知"""
        try:
            # 检查基本筛选条件
            volume = option_data.get('volume', 0)
            turnover = option_data.get('turnover', 0)
            
            if volume < OPTION_FILTER.get('min_volume', 100):
                return False
            
            if turnover < OPTION_FILTER.get('min_turnover', 50000):
                return False
            
            # 检查是否重复提醒
            option_code = option_data.get('option_code', '')
            current_time = datetime.now()
            
            if option_code in self.last_alerts:
                last_alert_time = self.last_alerts[option_code]
                time_diff = (current_time - last_alert_time).seconds
                if time_diff < 300:  # 5分钟内不重复提醒
                    return False
            
            # 记录提醒时间
            self.last_alerts[option_code] = current_time
            
            return True
            
        except Exception as e:
            self.logger.error(f"判断通知条件失败: {e}")
            return False
    
    def format_option_alert_message(self, option_data: Dict[str, Any]) -> str:
        """格式化期权提醒消息"""
        try:
            message = f"""🚨 期权大单提醒
📊 股票: {option_data.get('stock_name', 'Unknown')} ({option_data.get('stock_code', 'Unknown')})
🎯 期权: {option_data.get('option_code', 'Unknown')}
📈 类型: {option_data.get('option_type', 'Unknown')}
🔄 方向: {option_data.get('direction', 'Unknown')}
💰 价格: {option_data.get('price', 0):.2f} 港币
📦 数量: {option_data.get('volume', 0)} 手
💵 金额: {option_data.get('turnover', 0):,.0f} 港币
⚠️ 风险: {option_data.get('risk_level', 'Unknown')}
⭐ 重要性: {option_data.get('importance_score', 0)}/10
⏰ 时间: {option_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"""
            
            return message
            
        except Exception as e:
            self.logger.error(f"格式化提醒消息失败: {e}")
            return "期权大单提醒 - 数据解析错误"
    
    def save_enhanced_data(self, options_data: List[Dict[str, Any]]):
        """保存增强数据"""
        try:
            # 保存到JSON文件
            json_path = DATA_CONFIG.get('big_options_json', 'data/current_big_option.json')
            
            summary_data = {
                'timestamp': datetime.now().isoformat(),
                'total_trades': len(options_data),
                'total_amount': sum(opt.get('turnover', 0) for opt in options_data),
                'trades': options_data
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            # 保存到CSV文件
            if DATA_CONFIG.get('save_to_csv', False):
                csv_path = DATA_CONFIG.get('csv_path', 'data/option_trades.csv')
                df = pd.DataFrame(options_data)
                
                # 如果文件存在，追加数据
                try:
                    existing_df = pd.read_csv(csv_path)
                    df = pd.concat([existing_df, df], ignore_index=True)
                except FileNotFoundError:
                    pass
                
                df.to_csv(csv_path, index=False, encoding='utf-8')
            
            self.logger.info(f"已保存 {len(options_data)} 条增强期权数据")
            
        except Exception as e:
            self.logger.error(f"保存增强数据失败: {e}")
    
    def _parse_option_type(self, option_code: str) -> str:
        """解析期权类型"""
        if not option_code:
            return "Unknown"
        
        option_code_upper = option_code.upper()
        
        # 港股期权代码格式通常包含C(Call)或P(Put)
        if 'C' in option_code_upper:
            return "Call (看涨期权)"
        elif 'P' in option_code_upper:
            return "Put (看跌期权)"
        else:
            return "Unknown"
    
    def _parse_trade_direction(self, trade_direction: str) -> str:
        """解析交易方向"""
        if not trade_direction:
            return "Unknown"
        
        direction_upper = trade_direction.upper()
        
        if direction_upper in ['BUY', 'B', '买入']:
            return "买入 📈"
        elif direction_upper in ['SELL', 'S', '卖出']:
            return "卖出 📉"
        else:
            return f"{trade_direction} ❓"
    
    def _calculate_risk_level(self, option_data: Dict[str, Any]) -> str:
        """计算风险等级"""
        try:
            turnover = option_data.get('turnover', 0)
            volume = option_data.get('volume', 0)
            
            # 基于成交额和成交量判断风险等级
            if turnover >= 1000000 or volume >= 500:  # 100万港币或500手以上
                return "高风险 🔴"
            elif turnover >= 500000 or volume >= 200:  # 50万港币或200手以上
                return "中风险 🟡"
            else:
                return "低风险 🟢"
                
        except Exception as e:
            self.logger.error(f"计算风险等级失败: {e}")
            return "Unknown"
    
    def _calculate_importance_score(self, option_data: Dict[str, Any]) -> int:
        """计算重要性评分 (1-10分)"""
        try:
            score = 0
            
            # 成交额权重 (40%)
            turnover = option_data.get('turnover', 0)
            if turnover >= 2000000:
                score += 4
            elif turnover >= 1000000:
                score += 3
            elif turnover >= 500000:
                score += 2
            elif turnover >= 100000:
                score += 1
            
            # 成交量权重 (30%)
            volume = option_data.get('volume', 0)
            if volume >= 1000:
                score += 3
            elif volume >= 500:
                score += 2
            elif volume >= 200:
                score += 1
            
            # 期权类型权重 (20%)
            option_type = option_data.get('option_type', '')
            if 'Call' in option_type or 'Put' in option_type:
                score += 2
            
            # 交易方向权重 (10%)
            direction = option_data.get('direction', '')
            if '买入' in direction or '卖出' in direction:
                score += 1
            
            return min(score, 10)  # 最高10分
            
        except Exception as e:
            self.logger.error(f"计算重要性评分失败: {e}")
            return 5  # 默认中等重要性