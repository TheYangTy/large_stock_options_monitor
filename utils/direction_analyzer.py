#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
期权交易方向分析器
根据期权代码和价格变动推断交易方向
"""

import logging
from typing import Dict, Any, Optional

class DirectionAnalyzer:
    """期权交易方向分析器"""
    
    def __init__(self):
        """初始化分析器"""
        self.logger = logging.getLogger(__name__)
    
    def analyze_direction(self, option_data: Dict[str, Any]) -> str:
        """
        分析期权交易方向
        
        Args:
            option_data: 期权数据
            
        Returns:
            str: 交易方向 ("买入 📈", "卖出 📉", "未知")
        """
        try:
            # 1. 如果已有交易方向，直接返回
            if 'trade_direction' in option_data:
                direction = option_data['trade_direction'].upper()
                if direction in ['BUY', 'B', '买入']:
                    return "买入 📈"
                elif direction in ['SELL', 'S', '卖出']:
                    return "卖出 📉"
            
            # 2. 根据价格变动推断
            change_rate = option_data.get('change_rate', 0)
            if change_rate > 0:
                # 价格上涨，可能是买入压力
                return "买入 📈"
            elif change_rate < 0:
                # 价格下跌，可能是卖出压力
                return "卖出 📉"
            
            # 3. 根据期权类型和成交量推断
            option_code = option_data.get('option_code', '')
            volume = option_data.get('volume', 0)
            
            # 如果是大单，根据期权类型推断
            if volume >= 500:
                if 'C' in option_code.upper():  # Call期权
                    return "买入 📈"  # 大单Call通常是看涨买入
                elif 'P' in option_code.upper():  # Put期权
                    return "卖出 📉"  # 大单Put通常是看跌卖出
            
            # 4. 根据时间段推断
            # 这里可以添加更复杂的时间段分析逻辑
            
            # 5. 默认推断：根据期权代码
            # 阿里巴巴期权代码特殊处理
            if 'ALB' in option_code and 'C' in option_code.upper():
                return "买入 📈"  # 阿里巴巴Call期权假设为买入
            
            # 6. 无法确定方向
            return "未知"
            
        except Exception as e:
            self.logger.error(f"分析交易方向失败: {e}")
            return "未知"
    
    def get_direction_with_confidence(self, option_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取交易方向及置信度
        
        Args:
            option_data: 期权数据
            
        Returns:
            Dict: 包含方向和置信度的字典
        """
        direction = self.analyze_direction(option_data)
        
        # 计算置信度
        confidence = 0.5  # 默认中等置信度
        
        # 如果有明确的交易方向
        if 'trade_direction' in option_data:
            confidence = 0.9  # 高置信度
        # 如果有价格变动
        elif option_data.get('change_rate', 0) != 0:
            confidence = 0.7  # 较高置信度
        # 如果是大单
        elif option_data.get('volume', 0) >= 500:
            confidence = 0.6  # 中高置信度
        
        return {
            'direction': direction,
            'confidence': confidence
        }