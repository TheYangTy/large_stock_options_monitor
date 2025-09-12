# -*- coding: utf-8 -*-
"""
OpenD API管理器 - 专门负责与富途OpenD API的交互
"""

import time
import logging
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import futu as ft
from dataclasses import dataclass
from config import FUTU_CONFIG, MONITOR_STOCKS


@dataclass
class StockQuote:
    """股票报价数据结构"""
    code: str
    price: float
    volume: int
    turnover: float
    name: str
    update_time: datetime
    change_rate: float = 0.0


@dataclass
class OptionTrade:
    """期权交易数据结构"""
    option_code: str
    stock_code: str
    price: float
    volume: int
    turnover: float
    direction: str
    trade_time: datetime
    strike_price: float = 0.0
    option_type: str = ""
    expiry_date: str = ""


class APIManager:
    """OpenD API管理器 - 后台线程处理所有API交互"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.APIManager')
        self.quote_ctx = None
        self.is_running = False
        self.api_thread = None
        
        # 数据缓存
        self.stock_quotes_cache: Dict[str, StockQuote] = {}
        self.option_trades_cache: Dict[str, List[OptionTrade]] = {}
        
        # 订阅管理
        self.subscribed_stocks = set()
        self.subscribed_options = set()
        
        # 回调函数注册
        self.stock_quote_callbacks: List[Callable[[StockQuote], None]] = []
        self.option_trade_callbacks: List[Callable[[OptionTrade], None]] = []
        
        # 任务队列
        self.task_queue = queue.Queue()
        
        # 连接状态
        self.connection_status = False
        self.last_heartbeat = None
        
    def start(self):
        """启动API管理器"""
        if self.is_running:
            self.logger.warning("API管理器已在运行")
            return
            
        self.is_running = True
        self.api_thread = threading.Thread(target=self._api_loop, daemon=True)
        self.api_thread.start()
        self.logger.info("API管理器已启动")
        
    def stop(self):
        """停止API管理器"""
        self.is_running = False
        if self.api_thread and self.api_thread.is_alive():
            self.api_thread.join(timeout=5)
            
        if self.quote_ctx:
            try:
                self.quote_ctx.unsubscribe_all()
                self.quote_ctx.close()
            except Exception as e:
                self.logger.warning(f"关闭API连接时出错: {e}")
                
        self.logger.info("API管理器已停止")
        
    def _api_loop(self):
        """API主循环 - 在后台线程中运行"""
        self.logger.info("API后台线程已启动")
        
        # 初始化连接
        if not self._init_connection():
            self.logger.error("API连接初始化失败")
            return
            
        # 订阅监控股票
        self._subscribe_stocks(MONITOR_STOCKS)
        
        while self.is_running:
            try:
                # 处理任务队列
                self._process_tasks()
                
                # 心跳检测
                self._heartbeat_check()
                
                # 定期更新期权订阅
                self._update_option_subscriptions()
                
                time.sleep(1)  # 1秒循环
                
            except Exception as e:
                self.logger.error(f"API循环异常: {e}")
                time.sleep(5)
                
        self.logger.info("API后台线程已退出")
        
    def _init_connection(self) -> bool:
        """初始化Futu连接"""
        try:
            self.quote_ctx = ft.OpenQuoteContext(
                host=FUTU_CONFIG['host'],
                port=FUTU_CONFIG['port']
            )
            
            # 设置回调处理器
            self.quote_ctx.set_handler(StockQuoteHandler(self))
            self.quote_ctx.set_handler(OptionTickerHandler(self))
            
            self.connection_status = True
            self.last_heartbeat = datetime.now()
            self.logger.info("Futu OpenD连接成功")
            return True
            
        except Exception as e:
            self.logger.error(f"Futu OpenD连接失败: {e}")
            self.connection_status = False
            return False
            
    def _subscribe_stocks(self, stock_codes: List[str]):
        """订阅股票报价"""
        try:
            new_stocks = [code for code in stock_codes if code not in self.subscribed_stocks]
            if not new_stocks:
                return
                
            # 批量订阅
            batch_size = 50
            for i in range(0, len(new_stocks), batch_size):
                batch = new_stocks[i:i+batch_size]
                ret, data = self.quote_ctx.subscribe(batch, [ft.SubType.QUOTE])
                
                if ret == ft.RET_OK:
                    self.subscribed_stocks.update(batch)
                    self.logger.info(f"成功订阅 {len(batch)} 只股票")
                else:
                    self.logger.warning(f"订阅股票失败: {data}")
                    
                time.sleep(0.5)  # 避免API限流
                
        except Exception as e:
            self.logger.error(f"订阅股票异常: {e}")
            
    def _process_tasks(self):
        """处理任务队列"""
        try:
            while not self.task_queue.empty():
                task = self.task_queue.get_nowait()
                self._execute_task(task)
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"处理任务异常: {e}")
            
    def _execute_task(self, task: Dict[str, Any]):
        """执行具体任务"""
        task_type = task.get('type')
        
        if task_type == 'subscribe_options':
            option_codes = task.get('option_codes', [])
            self._subscribe_options(option_codes)
        elif task_type == 'get_option_chain':
            stock_code = task.get('stock_code')
            callback = task.get('callback')
            self._get_option_chain_async(stock_code, callback)
        elif task_type == 'get_stock_price':
            stock_code = task.get('stock_code')
            callback = task.get('callback')
            self._get_stock_price_async(stock_code, callback)
            
    def _subscribe_options(self, option_codes: List[str]):
        """订阅期权逐笔数据"""
        try:
            new_options = [code for code in option_codes if code not in self.subscribed_options]
            if not new_options:
                return
                
            batch_size = 10
            for i in range(0, len(new_options), batch_size):
                batch = new_options[i:i+batch_size]
                ret, data = self.quote_ctx.subscribe(batch, [ft.SubType.TICKER])
                
                if ret == ft.RET_OK:
                    self.subscribed_options.update(batch)
                    self.logger.debug(f"成功订阅 {len(batch)} 个期权")
                else:
                    self.logger.warning(f"订阅期权失败: {data}")
                    
                time.sleep(0.3)
                
        except Exception as e:
            self.logger.error(f"订阅期权异常: {e}")
            
    def _heartbeat_check(self):
        """心跳检测"""
        now = datetime.now()
        if self.last_heartbeat and (now - self.last_heartbeat).seconds > 300:  # 5分钟无响应
            self.logger.warning("API连接可能断开，尝试重连")
            self._reconnect()
            
    def _reconnect(self):
        """重新连接"""
        try:
            if self.quote_ctx:
                self.quote_ctx.close()
            self._init_connection()
            self._subscribe_stocks(list(self.subscribed_stocks))
        except Exception as e:
            self.logger.error(f"重连失败: {e}")
            
    def _update_option_subscriptions(self):
        """定期更新期权订阅"""
        # 每5分钟更新一次
        if not hasattr(self, '_last_option_update'):
            self._last_option_update = datetime.now()
            
        if (datetime.now() - self._last_option_update).seconds < 300:
            return
            
        # 这里可以实现智能的期权订阅更新逻辑
        self._last_option_update = datetime.now()
        
    # 公共接口方法
    def get_stock_quote(self, stock_code: str) -> Optional[StockQuote]:
        """获取股票报价（从缓存）"""
        return self.stock_quotes_cache.get(stock_code)
        
    def get_all_stock_quotes(self) -> Dict[str, StockQuote]:
        """获取所有股票报价"""
        return self.stock_quotes_cache.copy()
        
    def get_option_trades(self, option_code: str) -> List[OptionTrade]:
        """获取期权交易记录"""
        return self.option_trades_cache.get(option_code, [])
        
    def subscribe_option_codes(self, option_codes: List[str]):
        """异步订阅期权代码"""
        task = {
            'type': 'subscribe_options',
            'option_codes': option_codes
        }
        self.task_queue.put(task)
        
    def register_stock_quote_callback(self, callback: Callable[[StockQuote], None]):
        """注册股票报价回调"""
        self.stock_quote_callbacks.append(callback)
        
    def register_option_trade_callback(self, callback: Callable[[OptionTrade], None]):
        """注册期权交易回调"""
        self.option_trade_callbacks.append(callback)
        
    def _notify_stock_quote_callbacks(self, quote: StockQuote):
        """通知股票报价回调"""
        for callback in self.stock_quote_callbacks:
            try:
                callback(quote)
            except Exception as e:
                self.logger.error(f"股票报价回调异常: {e}")
                
    def _notify_option_trade_callbacks(self, trade: OptionTrade):
        """通知期权交易回调"""
        for callback in self.option_trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                self.logger.error(f"期权交易回调异常: {e}")
                
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            'connected': self.connection_status,
            'subscribed_stocks': len(self.subscribed_stocks),
            'subscribed_options': len(self.subscribed_options),
            'cached_quotes': len(self.stock_quotes_cache),
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None
        }


class StockQuoteHandler(ft.StockQuoteHandlerBase):
    """股票报价推送处理器"""
    
    def __init__(self, api_manager: APIManager):
        super().__init__()
        self.api_manager = api_manager
        self.logger = api_manager.logger
        
    def on_recv_rsp(self, rsp_pb):
        """处理股票报价推送"""
        ret_code, data = super().on_recv_rsp(rsp_pb)
        if ret_code != ft.RET_OK:
            return ret_code, data
            
        if not hasattr(data, 'empty') or data.empty:
            return ret_code, data
            
        # 更新缓存并通知回调
        for _, row in data.iterrows():
            quote = StockQuote(
                code=row['code'],
                price=float(row['last_price']),
                volume=int(row.get('volume', 0)),
                turnover=float(row.get('turnover', 0)),
                name=row.get('name', ''),
                update_time=datetime.now(),
                change_rate=float(row.get('change_rate', 0))
            )
            
            # 更新缓存
            self.api_manager.stock_quotes_cache[quote.code] = quote
            self.api_manager.last_heartbeat = datetime.now()
            
            # 通知回调
            self.api_manager._notify_stock_quote_callbacks(quote)
            
        return ret_code, data


class OptionTickerHandler(ft.TickerHandlerBase):
    """期权逐笔交易处理器"""
    
    def __init__(self, api_manager: APIManager):
        super().__init__()
        self.api_manager = api_manager
        self.logger = api_manager.logger
        
    def on_recv_rsp(self, rsp_pb):
        """处理期权逐笔推送"""
        ret_code, data = super().on_recv_rsp(rsp_pb)
        if ret_code != ft.RET_OK:
            return ret_code, data
            
        if not hasattr(data, 'empty') or data.empty:
            return ret_code, data
            
        # 处理期权交易数据
        for _, row in data.iterrows():
            # 解析股票代码
            option_code = row['code']
            stock_code = self._extract_stock_code(option_code)
            
            trade = OptionTrade(
                option_code=option_code,
                stock_code=stock_code,
                price=float(row['price']),
                volume=int(row['volume']),
                turnover=float(row['price']) * int(row['volume']),
                direction=row.get('ticker_direction', 'Unknown'),
                trade_time=datetime.now()
            )
            
            # 更新缓存
            if option_code not in self.api_manager.option_trades_cache:
                self.api_manager.option_trades_cache[option_code] = []
            self.api_manager.option_trades_cache[option_code].append(trade)
            
            # 保持最近100条记录
            if len(self.api_manager.option_trades_cache[option_code]) > 100:
                self.api_manager.option_trades_cache[option_code] = \
                    self.api_manager.option_trades_cache[option_code][-100:]
                    
            # 通知回调
            self.api_manager._notify_option_trade_callbacks(trade)
            
        return ret_code, data
        
    def _extract_stock_code(self, option_code: str) -> str:
        """从期权代码提取股票代码"""
        try:
            # 使用V2系统的统一期权代码解析器
            try:
                import sys
                import os
                # 添加v2_system路径到sys.path
                v2_system_path = os.path.join(os.path.dirname(__file__), '..')
                if v2_system_path not in sys.path:
                    sys.path.append(v2_system_path)
                from utils.option_code_parser import get_stock_code
                stock_code = get_stock_code(option_code)
                if stock_code:
                    return stock_code
            except ImportError as e:
                self.logger.error(f"导入V2期权解析器失败: {e}")
            
            # 兜底逻辑
            if option_code.startswith('HK.'):
                # 简单的提取逻辑，可以根据需要完善
                parts = option_code[3:].split('C')
                if len(parts) > 1:
                    return f"HK.{parts[0][:5]}"
                parts = option_code[3:].split('P')
                if len(parts) > 1:
                    return f"HK.{parts[0][:5]}"
            return "Unknown"
        except:
            return "Unknown"