# -*- coding: utf-8 -*-
"""
Web监控面板
增强版：支持企微推送和期权类型/交易方向展示
"""

from flask import Flask, render_template, jsonify, request, make_response
import json
import pandas as pd
import logging
import os
import traceback
import sys
from datetime import datetime
from option_monitor import OptionMonitor
from utils.data_handler import DataHandler
from utils.big_options_processor import BigOptionsProcessor
from utils.earnings_calendar import EarningsCalendar
from utils.push_record_manager import PushRecordManager
from config import WEB_CONFIG, NOTIFICATION, LOG_CONFIG

# 配置日志
def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, LOG_CONFIG.get('log_level', 'INFO')))
    
    # 创建日志目录
    log_dir = os.path.dirname(LOG_CONFIG.get('log_file', 'logs/web_dashboard.log'))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 文件处理器
    file_handler = logging.FileHandler('logs/web_dashboard.log')
    file_handler.setLevel(getattr(logging, LOG_CONFIG.get('log_level', 'INFO')))
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_CONFIG.get('log_level', 'INFO')))
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志
logger = setup_logger()

# 导入企微通知模块和方向分析器
try:
    from utils.wework_notifier import WeWorkNotifier
    
    wework_available = True
except ImportError:
    wework_available = False

app = Flask(__name__)
monitor = None
data_handler = DataHandler()
big_options_processor = BigOptionsProcessor()
# logger已在上面通过setup_logger()初始化

# 初始化企微通知器和方向分析器
wework_notifier = None
# direction analyzer removed per requirement
earnings_calendar = EarningsCalendar()
last_data_hash = None  # 用于跟踪数据变化

# 全局股价缓存
stock_price_cache = {}  # 股票代码 -> 价格
stock_price_cache_time = {}  # 股票代码 -> 缓存时间

# 初始化推送记录管理器
push_record_manager = PushRecordManager()

# 获取股票价格（带缓存）
def get_stock_price(stock_code, force_refresh=False):
    """获取股票价格，带缓存机制"""
    global stock_price_cache, stock_price_cache_time
    
    try:
        # 检查缓存是否有效
        current_time = datetime.now()
        cache_valid = (
            stock_code in stock_price_cache and 
            stock_code in stock_price_cache_time and
            not force_refresh and
            (current_time - stock_price_cache_time[stock_code]).total_seconds() < 300  # 5分钟缓存
        )
        
        if cache_valid:
            logger.debug(f"使用缓存的股价: {stock_code} = {stock_price_cache[stock_code]}")
            return stock_price_cache[stock_code]
        
        # 缓存无效，需要获取新数据
        logger.info(f"获取股价: {stock_code}")
        import futu as ft
        
        try:
            # 移除timeout参数，富途API不支持
            quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, data = quote_ctx.get_market_snapshot([stock_code])
            quote_ctx.close()
            
            if ret == ft.RET_OK and not data.empty:
                price = float(data.iloc[0]['last_price'])
                # 更新缓存
                stock_price_cache[stock_code] = price
                stock_price_cache_time[stock_code] = current_time
                logger.info(f"获取股价成功: {stock_code} = {price}")
                return price
            else:
                logger.warning(f"获取股价失败: {stock_code}, ret={ret}")
                return stock_price_cache.get(stock_code, 0)  # 返回缓存或0
        except Exception as e:
            logger.error(f"获取股价异常: {stock_code}, {e}")
            return stock_price_cache.get(stock_code, 0)  # 返回缓存或0
    except Exception as e:
        logger.error(f"股价获取处理异常: {e}")
        return 0

if wework_available and NOTIFICATION.get('enable_wework_bot', False):
    try:
        wework_config = NOTIFICATION.get('wework_config', {})
        webhook_url = wework_config.get('webhook_url', '')
        if webhook_url:
            wework_notifier = WeWorkNotifier(
                webhook_url=webhook_url,
                mentioned_list=wework_config.get('mentioned_list', []),
                mentioned_mobile_list=wework_config.get('mentioned_mobile_list', [])
            )
            logger.info("企微通知器初始化成功")
    except Exception as e:
        logger.error(f"企微通知器初始化失败: {e}")


@app.route('/')
def dashboard():
    """主面板"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """获取监控状态API"""
    global monitor
    
    if monitor is None:
        return jsonify({
            'status': 'stopped',
            'message': '监控未启动'
        })
    
    status = monitor.get_monitoring_status()
    stats = data_handler.get_statistics()
    
    return jsonify({
        'status': 'running' if status['is_running'] else 'stopped',
        'trading_time': status['trading_time'],
        'monitored_stocks': status['monitored_stocks'],
        'statistics': stats,
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/recent_trades')
def get_recent_trades():
    """获取最近交易API"""
    df = data_handler.load_historical_data(days=1)
    
    if df.empty:
        return jsonify([])
    
    # 转换为JSON格式
    trades = df.tail(20).to_dict('records')
    
    # 格式化时间戳
    for trade in trades:
        if 'timestamp' in trade:
            trade['timestamp'] = pd.to_datetime(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(trades)


# 添加CORS支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

@app.route('/api/big_options_summary')
def get_big_options_summary():
    """获取大单期权汇总API - 直接使用option_monitor.py生成的缓存数据"""
    global last_data_hash
    
    try:
        # 检查是否是首次加载
        is_first_load = request.args.get('first_load', 'false').lower() == 'true'
        logger.info(f"API调用: big_options_summary, first_load={is_first_load}")
        
        # 直接从缓存文件加载数据，不再调用Futu API
        summary = big_options_processor.load_current_summary()

        # 也从 stock_prices.json 补齐名称，保持与摘要一致
        stock_name_map = {}
        try:
            sp_path = os.path.join('data', 'stock_prices.json')
            if os.path.exists(sp_path):
                with open(sp_path, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                prices = sp.get('prices') if isinstance(sp, dict) else None
                if isinstance(prices, dict):
                    for code, info in prices.items():
                        if isinstance(info, dict):
                            name = info.get('name')
                            if name:
                                stock_name_map[code] = name
        except Exception as _e:
            logger.warning(f"读取stock_prices.json失败: {_e}")

        if summary and stock_name_map:
            bos = summary.get('big_options', [])
            if isinstance(bos, list):
                for opt in bos:
                    if isinstance(opt, dict):
                        code = opt.get('stock_code')
                        if code and not opt.get('stock_name'):
                            nm = stock_name_map.get(code)
                            if nm:
                                opt['stock_name'] = nm

        # 从 data/stock_prices.json 读取股票名称映射，补齐 big_options 的 stock_name
        stock_name_map = {}
        try:
            sp_path = os.path.join('data', 'stock_prices.json')
            if os.path.exists(sp_path):
                with open(sp_path, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                # 兼容结构: {"prices": {"HK.00700": {"price": 600, "name": "腾讯"}}}
                prices = sp.get('prices') if isinstance(sp, dict) else None
                if isinstance(prices, dict):
                    for code, info in prices.items():
                        if isinstance(info, dict):
                            name = info.get('name')
                            if name:
                                stock_name_map[code] = name
        except Exception as _e:
            logger.warning(f"读取stock_prices.json失败: {_e}")

        big_options = summary.get('big_options', []) if summary else []
        if isinstance(big_options, list) and stock_name_map:
            for opt in big_options:
                if isinstance(opt, dict):
                    code = opt.get('stock_code')
                    if code and not opt.get('stock_name'):
                        nm = stock_name_map.get(code)
                        if nm:
                            opt['stock_name'] = nm

        # 读取 stock_prices.json 中的成交额，补充到 big_options 的 stock_turnover 字段
        try:
            stock_turnover_map = {}
            sp_path = os.path.join('data', 'stock_prices.json')
            if os.path.exists(sp_path):
                with open(sp_path, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                prices = sp.get('prices') if isinstance(sp, dict) else None
                if isinstance(prices, dict):
                    for code, info in prices.items():
                        if isinstance(info, dict) and ('turnover' in info):
                            stock_turnover_map[code] = info.get('turnover')
            if isinstance(big_options, list) and stock_turnover_map:
                for opt in big_options:
                    if isinstance(opt, dict):
                        code = opt.get('stock_code')
                        if code and ('stock_turnover' not in opt):
                            t = stock_turnover_map.get(code)
                            if t is not None:
                                opt['stock_turnover'] = t
        except Exception as _e:
            logger.warning(f"读取stock_prices成交额失败: {_e}")
        
        logger.debug(f"从缓存加载汇总数据: {summary is not None}")
        if summary:
            logger.debug(f"汇总数据包含 {summary.get('total_count', 0)} 笔交易")
        
        if not summary:
            logger.warning("未找到缓存的汇总数据，请先运行option_monitor.py生成数据")
            return jsonify({
                'total_count': 0,
                'update_time': None,
                'lookback_days': 2,
                'statistics': {},
                'big_options': [],
                'debug_info': '未找到缓存数据，请先运行option_monitor.py'
            })
        
        # 增强数据：添加期权类型和交易方向
        big_options = summary.get('big_options', [])
        
        # 处理每个期权，确保所有必要字段都存在
        for option in big_options:
            # 确保期权类型字段存在
            if 'option_type' not in option or not option['option_type']:
                option_code = option.get('option_code', '')
                if 'C' in option_code.upper():
                    option['option_type'] = "Call (看涨期权)"
                elif 'P' in option_code.upper():
                    option['option_type'] = "Put (看跌期权)"
                else:
                    option['option_type'] = '未知'
            
            # 确保交易方向字段存在
            # 去掉交易方向推断
            # if 'direction' not in option or not option['direction'] or option['direction'] == '未知':
            #     option['direction'] = direction_analyzer.analyze_direction(option)
                
                # 如果方向仍然是未知，根据期权类型和成交量/价格变化推断
                if option['direction'] == '未知':
                    option_type = option.get('option_type', '')
                    change_rate = option.get('change_rate', 0)
                    
                    # 根据期权类型和价格变化推断方向
                    if 'Call' in option_type or '看涨' in option_type:
                        option['direction'] = '买入看涨' if change_rate >= 0 else '卖出看涨'
                    elif 'Put' in option_type or '看跌' in option_type:
                        option['direction'] = '买入看跌' if change_rate >= 0 else '卖出看跌'
                    else:
                        option_code = option.get('option_code', '')
                        if 'C' in option_code.upper():
                            option['direction'] = '买入看涨'
                        elif 'P' in option_code.upper():
                            option['direction'] = '买入看跌'
                        else:
                            option['direction'] = '买入'
        
        # 检查数据是否有变化
        current_data_hash = hash(str(summary))
        data_changed = last_data_hash is not None and current_data_hash != last_data_hash

        # 应用筛选器：按股票代码与股票名称（包含匹配，不区分大小写）
        code_filter = request.args.get('stock_code', '').strip()
        name_filter = request.args.get('stock_name', '').strip()
        if (code_filter or name_filter) and isinstance(big_options, list):
            cf = code_filter.lower()
            nf = name_filter.lower()
            def _match(opt):
                try:
                    code = str(opt.get('stock_code', '')).lower()
                    name = str(opt.get('stock_name', '')).lower()
                    okc = True if not cf else (cf in code)
                    okn = True if not nf else (nf in name)
                    return okc and okn
                except Exception:
                    return False
            before = len(big_options)
            big_options = [o for o in big_options if isinstance(o, dict) and _match(o)]
            logger.info(f"筛选: code='{code_filter}', name='{name_filter}' => {len(big_options)}/{before}")
        
        # 强制发送大单数据到企微
        # 推送逻辑已迁移到 option_monitor.py，此处禁用
        if False:
            try:
                # 发送汇总通知
                total_count = summary.get('total_count', 0)
                
                # 获取统计数据
                statistics = summary.get('statistics', {})
                total_turnover = statistics.get('total_turnover', 0)
                
                # 直接从big_options获取数据
                if total_count > 0 and big_options:
                    # 使用当前时间
                    from datetime import datetime
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 过滤出新增的大单期权
                    new_options = []
                    for option in big_options:
                        option_id = push_record_manager.generate_option_id(option)
                        if not push_record_manager.is_option_pushed(option_id):
                            new_options.append(option)
                            # 标记为已推送
                            push_record_manager.mark_option_pushed(option_id)
                    
                    # 如果有新增大单，则推送
                    new_count = len(new_options)
                    if new_count > 0:
                        message = f"""📊 港股期权大单监控
⏰ 时间: {current_time}
📈 总交易: {total_count} 笔
🆕 新增交易: {new_count} 笔
💰 总金额: {total_turnover:,.0f} 港币

📋 新增大单明细:"""
                        
                        # 添加最多5条新增大单明细
                        for i, option in enumerate(new_options[:5]):
                            stock_code = option.get('stock_code', 'Unknown')
                            stock_name = option.get('stock_name', '')
                            stock_display = f"{stock_name}({stock_code})" if stock_name else stock_code
                            option_code = option.get('option_code', 'Unknown')
                            option_type = option.get('option_type', '未知')
                            direction = option.get('direction', '未知')
                            volume = option.get('volume', 0)
                            turnover = option.get('turnover', 0)
                            
                            message += f"\n{i+1}. {stock_display} {option_code} {option_type} {volume}手 {turnover:,.0f}港币"
                        
                        if new_count > 5:
                            message += f"\n... 还有 {new_count - 5} 笔新增大单 (详见网页)"
                        
                        # 推送逻辑已迁移到 option_monitor.py，此处禁用发送
                        logger.info("已禁用：推送由 option_monitor.py 负责，此处不再发送企微通知")
                    else:
                        logger.info("没有新增大单，跳过推送")
            except Exception as e:
                logger.error(f"❌ 发送企微通知失败: {e}")
                logger.error(traceback.format_exc())
        
        # 更新数据哈希值
        last_data_hash = current_data_hash
        
        # 确保数据格式正确
        result = {
            'total_count': len(big_options) if isinstance(big_options, list) else summary.get('total_count', 0),
            'update_time': summary.get('update_time'),
            'lookback_days': summary.get('lookback_days', 2),
            'statistics': summary.get('statistics', {}),
            'big_options': big_options,
            'filter_conditions': summary.get('filter_conditions', {}),
            'debug_info': f"成功从缓存加载 {summary.get('total_count', 0)} 笔交易，并基于stock_prices.json补齐{len(stock_name_map) if 'stock_name_map' in locals() else 0}个名称"
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取大单汇总失败: {e}")
        logger.error(traceback.format_exc())
        
        # 创建一个带有错误信息的响应
        response = make_response(jsonify({
            'total_count': 0,
            'update_time': None,
            'lookback_days': 2,
            'statistics': {},
            'big_options': [],
            'error': str(e),
            'debug_info': f'API错误: {str(e)}'
        }))
        
        # 添加CORS头和缓存控制
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
        response.headers.add('Pragma', 'no-cache')
        response.headers.add('Expires', '0')
        
        return response


@app.route('/api/refresh_big_options')
def refresh_big_options():
    """强制刷新大单数据API - 基于option_monitor.py生成的缓存数据"""
    try:
        from datetime import datetime
        
        logger.info("开始刷新大单数据（从缓存文件）...")
        
        # 直接从缓存文件加载数据，不再调用Futu API
        summary = big_options_processor.load_current_summary()
        
        if not summary:
            logger.warning("未找到缓存的汇总数据，请先运行option_monitor.py生成数据")
            return jsonify({
                'success': False, 
                'message': '未找到缓存数据，请先运行option_monitor.py生成数据',
                'summary': None
            })
        
        # 更新时间戳，表示已刷新
        summary['update_time'] = datetime.now().isoformat()
        
        # 保存更新后的数据回文件
        try:
            import json
            with open(big_options_processor.json_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logger.info("已更新缓存文件的时间戳")
        except Exception as save_err:
            logger.error(f"更新缓存文件时间戳失败: {save_err}")
        
        if summary.get('total_count', 0) > 0:
            logger.info(f"刷新成功: {summary.get('total_count', 0)} 笔交易")
            return jsonify({
                'success': True, 
                'message': f'刷新成功，从缓存加载了 {summary.get("total_count", 0)} 笔大单',
                'summary': summary
            })
        else:
            logger.info("刷新完成，但缓存中无大单数据")
            return jsonify({
                'success': True, 
                'message': '刷新完成，缓存中暂无大单数据',
                'summary': None
            })
            
    except Exception as e:
        logger.error(f"刷新失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False, 
            'message': f'刷新失败: {e}'
        })


@app.route('/api/start_monitor')
def start_monitor():
    """启动监控API"""
    global monitor
    
    try:
        if monitor is None:
            monitor = OptionMonitor()
        
        monitor.start_monitoring()
        return jsonify({'success': True, 'message': '监控已启动'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {e}'})


@app.route('/api/stop_monitor')
def stop_monitor():
    """停止监控API"""
    global monitor
    
    try:
        if monitor:
            monitor.stop_monitoring()
        return jsonify({'success': True, 'message': '监控已停止'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {e}'})


@app.route('/api/send_wework_test')
def send_wework_test():
    """已禁用：推送逻辑统一由 option_monitor.py 负责"""
    return jsonify({'status': 'error', 'message': '已禁用：请在 option_monitor.py 中进行推送测试'})

@app.route('/api/force_push')
def force_push():
    """已禁用：推送逻辑统一由 option_monitor.py 负责"""
    return jsonify({'status': 'error', 'message': '已禁用：请在 option_monitor.py 中进行推送'})
    return jsonify({'status': 'error', 'message': '已禁用：请在 option_monitor.py 中进行推送'})
    if not wework_notifier:
        return jsonify({
            'status': 'error',
            'message': '企微通知器未初始化'
        })
    
    try:
        # 加载数据
        summary = big_options_processor.load_current_summary()
        if not summary:
            return jsonify({
                'status': 'error',
                'message': '无法加载大单数据'
            })
        
        # 解析数据
        big_options = summary.get('big_options', [])
        total_count = len(big_options)
        statistics = summary.get('statistics', {})
        total_turnover = statistics.get('total_turnover', 0)

        # 从 data/stock_prices.json 补齐股票名称
        try:
            stock_name_map = {}
            sp_path = os.path.join('data', 'stock_prices.json')
            if os.path.exists(sp_path):
                with open(sp_path, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                prices = sp.get('prices') if isinstance(sp, dict) else None
                if isinstance(prices, dict):
                    for code, info in prices.items():
                        if isinstance(info, dict):
                            nm = info.get('name')
                            if nm:
                                stock_name_map[code] = nm
            if isinstance(big_options, list) and stock_name_map:
                for opt in big_options:
                    if isinstance(opt, dict):
                        code = opt.get('stock_code')
                        if code and not opt.get('stock_name'):
                            nm = stock_name_map.get(code)
                            if nm:
                                opt['stock_name'] = nm
        except Exception as _e:
            logger.warning(f"force_push 补齐名称失败: {_e}")
        
        if total_count == 0:
            return jsonify({
                'status': 'warning',
                'message': '没有大单数据可推送'
            })
        
        # 构建消息
        from datetime import datetime
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 强制推送时，可以选择是否只推送新增大单
        force_all = request.args.get('force_all', 'false').lower() == 'true'
        
        if force_all:
            # 推送所有大单，但仍然标记为已推送
            for option in big_options:
                option_id = push_record_manager.generate_option_id(option)
                push_record_manager.mark_option_pushed(option_id)
            
            message = f"""📊 港股期权大单监控 (网页强制推送-全部)
⏰ 时间: {current_time}
📈 总交易: {total_count} 笔
💰 总金额: {total_turnover:,.0f} 港币

📋 大单明细:"""
            
            # 添加大单明细
            for i, option in enumerate(big_options[:5]):
                stock_code = option.get('stock_code', 'Unknown')
                option_code = option.get('option_code', 'Unknown')
                
                # 解析期权类型
                option_type = option.get('option_type', '未知')
                if not option_type or option_type == '未知':
                    if 'C' in option_code.upper():
                        option_type = "Call (看涨期权)"
                    elif 'P' in option_code.upper():
                        option_type = "Put (看跌期权)"
                
                # 解析交易方向
                direction = option.get('direction', '未知')
                
                volume = option.get('volume', 0)
                turnover = option.get('turnover', 0)
                
                stock_name = option.get('stock_name', '')
                stock_display = f"{stock_name}({stock_code})" if stock_name else stock_code
                message += f"\n{i+1}. {stock_display} {option_code} {option_type} {volume}手 {turnover:,.0f}港币"
            
            if total_count > 5:
                message += f"\n... 还有 {total_count - 5} 笔大单 (详见网页)"
        else:
            # 只推送新增大单
            new_options = []
            for option in big_options:
                option_id = push_record_manager.generate_option_id(option)
                if not push_record_manager.is_option_pushed(option_id):
                    new_options.append(option)
                    # 标记为已推送
                    push_record_manager.mark_option_pushed(option_id)
            
            new_count = len(new_options)
            if new_count == 0:
                return jsonify({
                    'status': 'warning',
                    'message': '没有新增大单数据可推送，所有大单已经推送过'
                })
            
            message = f"""📊 港股期权大单监控 (网页强制推送-新增)
⏰ 时间: {current_time}
📈 总交易: {total_count} 笔
🆕 新增交易: {new_count} 笔
💰 总金额: {total_turnover:,.0f} 港币

📋 新增大单明细:"""
            
            # 添加新增大单明细
            for i, option in enumerate(new_options[:5]):
                stock_code = option.get('stock_code', 'Unknown')
                option_code = option.get('option_code', 'Unknown')
                
                # 解析期权类型
                option_type = option.get('option_type', '未知')
                if not option_type or option_type == '未知':
                    if 'C' in option_code.upper():
                        option_type = "Call (看涨期权)"
                    elif 'P' in option_code.upper():
                        option_type = "Put (看跌期权)"
                
                # 解析交易方向
                direction = option.get('direction', '未知')
                
                volume = option.get('volume', 0)
                turnover = option.get('turnover', 0)
                
                stock_name = option.get('stock_name', '')
                stock_display = f"{stock_name}({stock_code})" if stock_name else stock_code
                message += f"\n{i+1}. {stock_display} {option_code} {option_type} {volume}手 {turnover:,.0f}港币"
            
            if new_count > 5:
                message += f"\n... 还有 {new_count - 5} 笔新增大单 (详见网页)"
        
        # 发送消息
        logger.info("已禁用：web_dashboard 不再直接发送企微通知")
        success = False
        
        if success:
            if force_all:
                return jsonify({
                    'status': 'success',
                    'message': f'成功推送全部 {total_count} 笔大单数据到企微'
                })
            else:
                return jsonify({
                    'status': 'success',
                    'message': f'成功推送 {len(new_options)} 笔新增大单数据到企微'
                })
        else:
            return jsonify({
                'status': 'error',
                'message': '企微消息发送失败'
            })
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            'status': 'error',
            'message': f'推送异常: {str(e)}',
            'trace': error_trace
        })


if __name__ == '__main__':
    logger.info(f"🌐 启动Web监控面板 (增强版)")
    logger.info(f"📍 访问地址: http://localhost:{WEB_CONFIG['port']}")
    logger.info(f"🔧 如需修改端口，请编辑 config.py 中的 WEB_CONFIG")
    
    if wework_notifier:
        logger.info(f"🤖 企微机器人: 已启用")
    else:
        logger.info(f"🤖 企微机器人: 未启用")
    
    app.run(
        debug=WEB_CONFIG['debug'],
        host=WEB_CONFIG['host'],
        port=WEB_CONFIG['port']
    )