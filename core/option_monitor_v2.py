# -*- coding: utf-8 -*-
"""
优化版期权监控器 - 使用新的架构设计
"""

import time
import logging
import threading
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd

from config_v2 import MONITOR_STOCKS, OPTION_FILTERS, TRADING_HOURS
from utils.logger import setup_logger
from core.api_manager import APIManager, StockQuote, OptionTrade
from core.database_manager import DatabaseManager, OptionRecord
from core.option_analyzer import OptionAnalyzer
from core.notification_manager import V2NotificationManager, NotificationData


class OptionMonitorV2:
    """优化版期权监控器"""
    
    def __init__(self):
        self.logger = setup_logger()
        
        # 核心组件
        self.api_manager = APIManager()
        self.db_manager = DatabaseManager()
        self.option_analyzer = OptionAnalyzer()
        self.notification_manager = V2NotificationManager()
        
        # 运行状态
        self.is_running = False
        self.monitor_thread = None
        
        # 数据缓存
        self.processed_trades = set()  # 已处理的交易ID
        self.last_analysis_time = None
        
        # 注册回调
        self._register_callbacks()
        
    def _register_callbacks(self):
        """注册API回调函数"""
        # 股票报价回调
        self.api_manager.register_stock_quote_callback(self._on_stock_quote)
        
        # 期权交易回调
        self.api_manager.register_option_trade_callback(self._on_option_trade)
        
    def _on_stock_quote(self, quote: StockQuote):
        """处理股票报价推送"""
        try:
            # 保存股票价格历史
            self.db_manager.save_stock_price(
                stock_code=quote.code,
                stock_name=quote.name,
                price=quote.price,
                volume=quote.volume,
                turnover=quote.turnover,
                change_rate=quote.change_rate
            )
            
            self.logger.debug(f"股价更新: {quote.code} = {quote.price}")
            
        except Exception as e:
            self.logger.error(f"处理股票报价异常: {e}")
            
    def _on_option_trade(self, trade: OptionTrade):
        """处理期权交易推送"""
        try:
            # 生成交易ID
            trade_id = f"{trade.option_code}_{trade.trade_time.timestamp()}_{trade.volume}"
            
            # 避免重复处理
            if trade_id in self.processed_trades:
                return
                
            self.processed_trades.add(trade_id)
            
            # 获取股票报价
            stock_quote = self.api_manager.get_stock_quote(trade.stock_code)
            
            # 分析期权交易
            analysis_result = self.option_analyzer.analyze_option_trade(trade, stock_quote)
            
            # 检查是否为大单
            if analysis_result.get('is_big_trade', False):
                self._process_big_trade(trade, analysis_result, stock_quote)
                
        except Exception as e:
            self.logger.error(f"处理期权交易异常: {e}")
            
    def _process_big_trade(self, trade: OptionTrade, analysis: Dict[str, Any], stock_quote: StockQuote = None):
        """处理大单交易"""
        try:
            # 创建期权记录
            record = OptionRecord(
                timestamp=trade.trade_time,
                stock_code=trade.stock_code,
                stock_name=stock_quote.name if stock_quote else "",
                stock_price=stock_quote.price if stock_quote else 0.0,
                option_code=trade.option_code,
                option_type=analysis.get('option_type', ''),
                strike_price=analysis.get('strike_price', 0.0),
                expiry_date=analysis.get('expiry_date', ''),
                option_price=trade.price,
                volume=trade.volume,
                turnover=trade.turnover,
                direction=trade.direction,
                change_rate=analysis.get('change_rate', 0.0),
                implied_volatility=analysis.get('implied_volatility', 0.0),
                delta=analysis.get('delta', 0.0),
                gamma=analysis.get('gamma', 0.0),
                theta=analysis.get('theta', 0.0),
                vega=analysis.get('vega', 0.0),
                time_value=analysis.get('time_value', 0.0),
                intrinsic_value=analysis.get('intrinsic_value', 0.0),
                moneyness=analysis.get('moneyness', ''),
                days_to_expiry=analysis.get('days_to_expiry', 0),
                volume_diff=analysis.get('volume_diff', 0),
                last_volume=analysis.get('last_volume', 0),
                is_big_trade=True,
                risk_level=analysis.get('risk_level', ''),
                importance_score=analysis.get('importance_score', 0),
                raw_data=str(analysis)
            )
            
            # 保存到数据库
            record_id = self.db_manager.save_option_record(record)
            
            # 发送通知
            self._send_big_trade_notification(record, analysis)
            
            self.logger.info(f"🔥 发现大单: {trade.option_code}, 记录ID: {record_id}")
            
        except Exception as e:
            self.logger.error(f"处理大单交易异常: {e}")
            
    def _send_big_trade_notification(self, record: OptionRecord, analysis: Dict[str, Any]):
        """发送大单通知"""
        try:
            # 构建V2通知数据
            notification_data = NotificationData(
                stock_code=record.stock_code,
                stock_name=record.stock_name,
                option_code=record.option_code,
                option_type=record.option_type,
                strike_price=record.strike_price,
                expiry_date=record.expiry_date,
                price=record.option_price,
                volume=record.volume,
                turnover=record.turnover,
                direction=record.direction,
                timestamp=record.timestamp,
                volume_diff=record.volume_diff,
                last_volume=record.last_volume,
                risk_level=record.risk_level,
                importance_score=record.importance_score,
                moneyness=record.moneyness,
                days_to_expiry=record.days_to_expiry
            )
            
            # 发送V2通知
            self.notification_manager.send_big_trade_notification(notification_data)
            
        except Exception as e:
            self.logger.error(f"发送大单通知异常: {e}")
            
    def start_monitoring(self):
        """启动监控"""
        if self.is_running:
            self.logger.warning("监控已在运行中")
            return
            
        self.logger.info("启动期权监控系统V2...")
        
        # 启动API管理器
        self.api_manager.start()
        
        # 等待API连接建立
        time.sleep(3)
        
        # 启动监控线程
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("期权监控系统V2已启动")
        
    def stop_monitoring(self):
        """停止监控"""
        self.logger.info("停止期权监控系统V2...")
        
        self.is_running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        # 停止API管理器
        self.api_manager.stop()
        
        self.logger.info("期权监控系统V2已停止")
        
    def _monitor_loop(self):
        """监控主循环"""
        self.logger.info("监控主循环已启动")
        
        while self.is_running:
            try:
                # 定期分析和汇总
                self._periodic_analysis()
                
                # 清理旧数据
                self._cleanup_old_data()
                
                # 等待下一次循环
                time.sleep(60)  # 1分钟循环
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(10)
                
        self.logger.info("监控主循环已退出")
        
    def _periodic_analysis(self):
        """定期分析"""
        try:
            now = datetime.now()
            
            # 每5分钟执行一次完整分析
            if (self.last_analysis_time is None or 
                (now - self.last_analysis_time).seconds >= 300):
                
                self._comprehensive_analysis()
                self.last_analysis_time = now
                
        except Exception as e:
            self.logger.error(f"定期分析异常: {e}")
            
    def _comprehensive_analysis(self):
        """综合分析"""
        try:
            self.logger.info("执行综合分析...")
            
            # 获取最近的大单交易
            big_trades = self.db_manager.get_big_trades(hours=2)
            
            if not big_trades:
                self.logger.info("未发现新的大单交易")
                return
                
            # 按股票分组分析
            stock_analysis = self._analyze_by_stock(big_trades)
            
            # 发送汇总通知
            self._send_summary_notification(stock_analysis)
            
            self.logger.info(f"综合分析完成，发现 {len(big_trades)} 笔大单")
            
        except Exception as e:
            self.logger.error(f"综合分析异常: {e}")
            
    def _analyze_by_stock(self, trades: List[OptionRecord]) -> Dict[str, Any]:
        """按股票分析交易"""
        stock_groups = {}
        
        for trade in trades:
            stock_code = trade.stock_code
            if stock_code not in stock_groups:
                stock_groups[stock_code] = {
                    'stock_name': trade.stock_name,
                    'trades': [],
                    'total_volume': 0,
                    'total_turnover': 0.0,
                    'call_volume': 0,
                    'put_volume': 0,
                    'avg_importance': 0
                }
                
            group = stock_groups[stock_code]
            group['trades'].append(trade)
            group['total_volume'] += trade.volume
            group['total_turnover'] += trade.turnover
            
            if trade.option_type == 'Call':
                group['call_volume'] += trade.volume
            elif trade.option_type == 'Put':
                group['put_volume'] += trade.volume
                
        # 计算平均重要性分数
        for group in stock_groups.values():
            if group['trades']:
                group['avg_importance'] = sum(t.importance_score for t in group['trades']) / len(group['trades'])
                
        return stock_groups
        
    def _send_summary_notification(self, stock_analysis: Dict[str, Any]):
        """发送汇总通知"""
        try:
            if not stock_analysis:
                return
                
            # 构建V2汇总数据
            summary_notifications = []
            for stock_code, group in stock_analysis.items():
                for trade in group['trades']:
                    notification_data = NotificationData(
                        stock_code=trade.stock_code,
                        stock_name=trade.stock_name,
                        option_code=trade.option_code,
                        option_type=trade.option_type,
                        strike_price=trade.strike_price,
                        expiry_date=trade.expiry_date,
                        price=trade.option_price,
                        volume=trade.volume,
                        turnover=trade.turnover,
                        direction=trade.direction,
                        timestamp=trade.timestamp,
                        volume_diff=trade.volume_diff,
                        last_volume=trade.last_volume,
                        risk_level=trade.risk_level,
                        importance_score=trade.importance_score,
                        moneyness=trade.moneyness,
                        days_to_expiry=trade.days_to_expiry
                    )
                    summary_notifications.append(notification_data)
                    
            # 发送V2汇总通知
            self.notification_manager.send_summary_notification(summary_notifications)
            
        except Exception as e:
            self.logger.error(f"发送汇总通知异常: {e}")
            
    def _cleanup_old_data(self):
        """清理旧数据"""
        try:
            # 每小时清理一次
            if not hasattr(self, '_last_cleanup') or \
               (datetime.now() - self._last_cleanup).seconds >= 3600:
                
                # 清理内存中的已处理交易ID
                cutoff_time = datetime.now() - timedelta(hours=2)
                self.processed_trades = {
                    trade_id for trade_id in self.processed_trades
                    if '_' in trade_id and 
                    datetime.fromtimestamp(float(trade_id.split('_')[1])) > cutoff_time
                }
                
                # 清理数据库旧数据
                self.db_manager.cleanup_old_data(days=30)
                
                self._last_cleanup = datetime.now()
                
        except Exception as e:
            self.logger.error(f"清理旧数据异常: {e}")
            
    def get_monitoring_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        try:
            api_status = self.api_manager.get_connection_status()
            db_stats = self.db_manager.get_statistics(hours=24)
            
            return {
                'is_running': self.is_running,
                'api_status': api_status,
                'database_stats': db_stats,
                'processed_trades_count': len(self.processed_trades),
                'last_analysis_time': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
                'monitor_stocks': MONITOR_STOCKS
            }
            
        except Exception as e:
            self.logger.error(f"获取监控状态异常: {e}")
            return {'error': str(e)}
            
    def force_analysis(self):
        """强制执行分析"""
        try:
            self.logger.info("强制执行分析...")
            self._comprehensive_analysis()
            return True
        except Exception as e:
            self.logger.error(f"强制分析失败: {e}")
            return False
            
    def export_data(self, start_date: datetime, end_date: datetime, output_path: str):
        """导出数据"""
        try:
            self.db_manager.export_data(start_date, end_date, output_path)
            self.logger.info(f"数据导出完成: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"数据导出失败: {e}")
            return False


def signal_handler(signum, frame):
    """信号处理器"""
    print("\n收到停止信号，正在关闭监控...")
    if 'monitor' in globals():
        monitor.stop_monitoring()
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 创建监控器实例
        global monitor
        monitor = OptionMonitorV2()
        
        # 启动监控
        monitor.start_monitoring()
        
        # 保持程序运行
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"程序启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()