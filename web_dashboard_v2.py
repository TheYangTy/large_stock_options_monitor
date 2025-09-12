#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
港股期权大单监控系统 V2.0 - Web仪表板
"""

import os
import sys
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.database_manager import DatabaseManager
    from core.api_manager import APIManager
    from config import WEB_CONFIG, MONITOR_STOCKS
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保已安装所有依赖: pip install -r requirements_v2.txt")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

# 全局变量
db_manager = None
api_manager = None

def init_components():
    """初始化组件"""
    global db_manager, api_manager
    try:
        db_manager = DatabaseManager()
        # API管理器在Web模式下不启动，只用于查询
        print("Web仪表板组件初始化成功")
    except Exception as e:
        print(f"组件初始化失败: {e}")

@app.route('/')
def index():
    """主页"""
    return render_template('dashboard_v2.html')

@app.route('/api/status')
def get_status():
    """获取系统状态"""
    try:
        # 模拟API状态（Web模式下）
        api_status = {
            'connected': False,
            'subscribed_stocks': len(MONITOR_STOCKS),
            'subscribed_options': 0,
            'cached_quotes': 0
        }
        
        # 数据库统计
        db_stats = {}
        if db_manager:
            db_stats = db_manager.get_statistics(hours=24)
        
        return jsonify({
            'success': True,
            'api_status': api_status,
            'database_stats': db_stats,
            'monitor_stocks': MONITOR_STOCKS,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/big_trades')
def get_big_trades():
    """获取大单交易"""
    try:
        hours = request.args.get('hours', 24, type=int)
        stock_codes = request.args.getlist('stock_codes')
        
        if not stock_codes:
            stock_codes = None
            
        trades = []
        if db_manager:
            trade_records = db_manager.get_big_trades(hours=hours, stock_codes=stock_codes)
            
            for record in trade_records:
                trade_dict = {
                    'id': record.id,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'time': record.timestamp.strftime('%H:%M:%S') if record.timestamp else '',
                    'stock_code': record.stock_code,
                    'stock_name': record.stock_name,
                    'stock_price': record.stock_price,
                    'option_code': record.option_code,
                    'option_type': record.option_type,
                    'strike_price': record.strike_price,
                    'expiry_date': record.expiry_date,
                    'option_price': record.option_price,
                    'volume': record.volume,
                    'turnover': record.turnover,
                    'direction': record.direction,
                    'implied_volatility': record.implied_volatility,
                    'delta': record.delta,
                    'moneyness': record.moneyness,
                    'days_to_expiry': record.days_to_expiry,
                    'risk_level': record.risk_level,
                    'importance_score': record.importance_score
                }
                trades.append(trade_dict)
        
        return jsonify({
            'success': True,
            'trades': trades,
            'total': len(trades)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/stock_quotes')
def get_stock_quotes():
    """获取股票报价（从数据库获取最新价格）"""
    try:
        quotes = {}
        if db_manager:
            # 获取最新的股票价格
            for stock_code in MONITOR_STOCKS:
                latest_price = db_manager.get_latest_stock_price(stock_code)
                if latest_price:
                    quotes[stock_code] = {
                        'code': stock_code,
                        'name': latest_price.get('stock_name', stock_code),
                        'price': latest_price.get('price', 0.0),
                        'volume': latest_price.get('volume', 0),
                        'turnover': latest_price.get('turnover', 0.0),
                        'change_rate': latest_price.get('change_rate', 0.0),
                        'update_time': latest_price.get('timestamp', datetime.now()).isoformat()
                    }
        
        return jsonify({
            'success': True,
            'quotes': quotes
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/option_history/<option_code>')
def get_option_history(option_code):
    """获取期权历史"""
    try:
        days = request.args.get('days', 7, type=int)
        
        history = []
        if db_manager:
            records = db_manager.get_option_history(option_code, days=days)
            
            for record in records:
                history_dict = {
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'option_price': record.option_price,
                    'volume': record.volume,
                    'turnover': record.turnover,
                    'implied_volatility': record.implied_volatility,
                    'delta': record.delta
                }
                history.append(history_dict)
        
        return jsonify({
            'success': True,
            'history': history,
            'option_code': option_code
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/stock_price_history/<stock_code>')
def get_stock_price_history(stock_code):
    """获取股票价格历史"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        history = []
        if db_manager:
            df = db_manager.get_stock_price_history(stock_code, hours=hours)
            
            if not df.empty:
                history = df.to_dict('records')
                # 转换时间格式
                for record in history:
                    if 'timestamp' in record and hasattr(record['timestamp'], 'isoformat'):
                        record['timestamp'] = record['timestamp'].isoformat()
        
        return jsonify({
            'success': True,
            'history': history,
            'stock_code': stock_code
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/export')
def export_data():
    """导出数据"""
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        format_type = request.args.get('format', 'csv')
        
        if not start_date_str or not end_date_str:
            return jsonify({
                'success': False,
                'error': '请提供开始和结束日期'
            })
        
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"options_export_{timestamp}.{format_type}"
        
        # 确保data目录存在
        os.makedirs('data', exist_ok=True)
        output_path = os.path.join('data', filename)
        
        if db_manager:
            success = db_manager.export_data(start_date, end_date, output_path, format_type)
            
            if success and os.path.exists(output_path):
                return send_file(output_path, as_attachment=True, download_name=filename)
            else:
                return jsonify({
                    'success': False,
                    'error': '导出失败'
                })
        else:
            return jsonify({
                'success': False,
                'error': '数据库管理器未初始化'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/statistics')
def get_statistics():
    """获取统计信息"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        stats = {}
        if db_manager:
            stats = db_manager.get_detailed_statistics(hours=hours)
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': '页面未找到'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500

if __name__ == '__main__':
    # 初始化组件
    init_components()
    
    # 获取配置
    try:
        web_config = WEB_CONFIG
    except:
        web_config = {
            'host': '0.0.0.0',
            'port': 8288,
            'debug': False
        }
    
    print(f"启动Web仪表板...")
    print(f"访问地址: http://localhost:{web_config.get('port', 8288)}")
    
    # 启动Web服务器
    app.run(
        host=web_config.get('host', '0.0.0.0'),
        port=web_config.get('port', 8288),
        debug=web_config.get('debug', False)
    )