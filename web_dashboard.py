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

        # 从 data/stock_prices.json 读取股票名称和成交额信息
        stock_name_map = {}
        stock_turnover_map = {}
        prices = {}  # 定义prices变量，确保后续代码可以访问
        try:
            sp_path = os.path.join('data', 'stock_prices.json')
            if os.path.exists(sp_path):
                with open(sp_path, 'r', encoding='utf-8') as f:
                    sp = json.load(f)
                # 兼容结构: {"prices": {"HK.00700": {"price": 600, "name": "腾讯", "turnover": 1000000}}}
                prices = sp.get('prices') if isinstance(sp, dict) else {}
                if isinstance(prices, dict):
                    for code, info in prices.items():
                        if isinstance(info, dict):
                            # 获取股票名称
                            name = info.get('name')
                            if name:
                                stock_name_map[code] = name
                            
                            # 获取股票成交额
                            turnover = info.get('turnover')
                            if turnover is not None:
                                stock_turnover_map[code] = turnover
                    
                    logger.info(f"从stock_prices.json读取了{len(stock_name_map)}个股票名称和{len(stock_turnover_map)}个成交额数据")
        except Exception as e:
            logger.warning(f"读取stock_prices.json失败: {e}")

        # 补充股票名称和成交额到big_options
        big_options = summary.get('big_options', []) if summary else []
        if isinstance(big_options, list):
            updated_name_count = 0
            updated_turnover_count = 0
            
            for opt in big_options:
                if isinstance(opt, dict):
                    code = opt.get('stock_code')
                    if code:
                        # 补充股票名称
                        if not opt.get('stock_name') and code in stock_name_map:
                            opt['stock_name'] = stock_name_map[code]
                            updated_name_count += 1
                        
                        # 补充股票成交额 - 始终更新，确保使用最新数据
                        if code in stock_turnover_map:
                            opt['stock_turnover'] = stock_turnover_map[code]
                            updated_turnover_count += 1
            
            if updated_name_count > 0 or updated_turnover_count > 0:
                logger.info(f"已补充{updated_name_count}个股票名称和{updated_turnover_count}个成交额数据")
            
            # 如仍有缺失成交额的股票，尝试请求补齐；若失败，延迟10秒重试从缓存读取
            try:
                missing_codes = sorted(list({opt.get('stock_code') for opt in big_options
                                             if isinstance(opt, dict) and opt.get('stock_code')
                                             and (opt.get('stock_turnover') is None or float(opt.get('stock_turnover') or 0) == 0)}))
            except Exception:
                missing_codes = []
            if missing_codes:
                logger.info(f"发现{len(missing_codes)}只股票缺少成交额，尝试从行情接口补齐")
                # 行情请求补齐
                try:
                    import futu as ft
                    quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
                    ret_m, df_m = quote_ctx.get_market_snapshot(missing_codes)
                    quote_ctx.close()
                    if ret_m == ft.RET_OK and df_m is not None and not df_m.empty:
                        for _, r in df_m.iterrows():
                            c = r.get('code')
                            if c:
                                tv = r.get('turnover', None)
                                if tv is not None:
                                    try:
                                        stock_turnover_map[c] = float(tv)
                                    except Exception:
                                        pass
                        logger.info("已尝试通过行情接口补齐成交额")
                except Exception as _e:
                    logger.warning(f"行情补齐成交额失败: {_e}")
                # 二次回填到big_options
                try:
                    fixed = 0
                    for opt in big_options:
                        code = opt.get('stock_code')
                        if code and code in stock_turnover_map and (opt.get('stock_turnover') is None or float(opt.get('stock_turnover') or 0) == 0):
                            opt['stock_turnover'] = stock_turnover_map[code]
                            fixed += 1
                    if fixed:
                        logger.info(f"行情补齐后，已为{fixed}条记录填充成交额")
                except Exception:
                    pass
                # 若仍缺失，延迟10秒后重读缓存文件再尝试
                try:
                    still_missing = [opt.get('stock_code') for opt in big_options
                                     if isinstance(opt, dict) and opt.get('stock_code')
                                     and (opt.get('stock_turnover') is None or float(opt.get('stock_turnover') or 0) == 0)]
                    if still_missing:
                        logger.info("仍有成交额缺失，10秒后重试从缓存读取")
                        import time
                        time.sleep(10)
                        sp_path2 = os.path.join('data', 'stock_prices.json')
                        if os.path.exists(sp_path2):
                            with open(sp_path2, 'r', encoding='utf-8') as f2:
                                sp2 = json.load(f2)
                            prices2 = sp2.get('prices') if isinstance(sp2, dict) else {}
                            if isinstance(prices2, dict):
                                for code2 in still_missing:
                                    info2 = prices2.get(code2)
                                    if isinstance(info2, dict) and ('turnover' in info2) and (info2.get('turnover') is not None):
                                        stock_turnover_map[code2] = info2['turnover']
                        # 再次回填
                        fixed2 = 0
                        for opt in big_options:
                            code = opt.get('stock_code')
                            if code and code in stock_turnover_map and (opt.get('stock_turnover') is None or float(opt.get('stock_turnover') or 0) == 0):
                                opt['stock_turnover'] = stock_turnover_map[code]
                                fixed2 += 1
                        if fixed2:
                            logger.info(f"缓存重试后，已额外填充{fixed2}条成交额")
                except Exception as _e2:
                    logger.warning(f"缓存延迟重试失败: {_e2}")

        # 确保所有期权都有正确的正股股价和成交额数据
        logger.debug(f"确保所有期权都有正确的正股股价和成交额数据")
        
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
            # 获取股票代码
            stock_code = option.get('stock_code')
            
            # 处理正股股价：如果stock_price是对象，提取price字段
            if 'stock_price' in option and isinstance(option['stock_price'], dict):
                stock_price_info = option['stock_price']
                option['stock_price'] = stock_price_info.get('price', 0)
                # 如果没有stock_name，从stock_price对象中获取
                if not option.get('stock_name') and stock_price_info.get('name'):
                    option['stock_name'] = stock_price_info.get('name')
                # 处理正股成交额：从stock_price对象中提取turnover
                if 'turnover' in stock_price_info:
                    option['stock_turnover'] = stock_price_info.get('turnover')
            
            # 确保股票代码存在，并从stock_turnover_map中获取最新成交额
            if stock_code and stock_code in stock_turnover_map:
                option['stock_turnover'] = stock_turnover_map[stock_code]
                
            # 确保正股股价存在，如果不存在则从stock_prices.json中获取
            if stock_code and ('stock_price' not in option or option['stock_price'] == 0):
                if 'prices' in locals() and stock_code in prices and isinstance(prices[stock_code], dict) and 'price' in prices[stock_code]:
                    option['stock_price'] = prices[stock_code]['price']
            
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
        
        # 更新数据哈希值
        last_data_hash = current_data_hash
        
        # 对数据进行排序：首先按股票分组，然后在相同股票内按成交额排序
        if isinstance(big_options, list) and big_options:
            # 定义股票顺序映射（可以根据需要调整顺序）
            stock_order = {
                'HK.00700': 1,  # 腾讯控股
                'HK.09988': 2,  # 阿里巴巴
                'HK.03690': 3,  # 美团
                'HK.01810': 4,  # 小米集团
                'HK.09618': 5,  # 京东集团
                'HK.02318': 6,  # 中国平安
                'HK.00388': 7,  # 香港交易所
                'HK.00981': 8,  # 中芯国际
            }
            
            def sort_key(option):
                stock_code = option.get('stock_code', '')
                # 成交量优先排序（降序），类型不确定时安全转换
                vol = option.get('volume', 0)
                try:
                    vol = int(vol)
                except Exception:
                    vol = 0
                # 成交额次序（降序），保证为float
                try:
                    to = float(option.get('turnover', 0))
                except Exception:
                    to = 0.0
                # 获取股票排序权重，未知股票排在最后
                stock_weight = stock_order.get(stock_code, 999)
                # 为确保稳定性，加入股票代码作为次级分组键
                sc = str(stock_code)
                # 返回排序键：(股票权重, 股票代码, -成交量, -成交额)
                return (stock_weight, sc, -vol, -to)
            
            big_options.sort(key=sort_key)
            logger.debug(f"已对 {len(big_options)} 笔交易进行排序：按股票分组，组内按成交量、成交额降序")
        
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