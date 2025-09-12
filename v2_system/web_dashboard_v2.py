# -*- coding: utf-8 -*-
"""
V2系统Web监控面板
"""

import os
import sys
import json
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request

# 添加V2系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import *
from utils.logger import setup_logger
from utils.data_handler import V2DataHandler
from option_monitor_v2 import V2OptionMonitor

app = Flask(__name__)
logger = setup_logger('V2WebDashboard')
data_handler = V2DataHandler()
monitor = None

@app.route('/')
def index():
    """主页"""
    return render_template('dashboard_v2.html')

@app.route('/api/status')
def get_status():
    """获取系统状态"""
    try:
        if monitor:
            status = monitor.get_status()
        else:
            status = {
                'is_running': False,
                'system_version': 'V2',
                'message': '监控器未初始化'
            }
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/big_options')
def get_big_options():
    """获取大单期权数据"""
    try:
        # 获取查询参数
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        # 从数据处理器获取数据
        big_options = data_handler.get_recent_big_options(hours=hours, limit=limit)
        
        return jsonify({
            'success': True,
            'data': big_options,
            'count': len(big_options)
        })
    except Exception as e:
        logger.error(f"获取大单期权数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/statistics')
def get_statistics():
    """获取统计数据"""
    try:
        stats = data_handler.get_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/start_monitor', methods=['POST'])
def start_monitor():
    """启动监控"""
    try:
        global monitor
        if not monitor:
            monitor = V2OptionMonitor()
        
        if not monitor.is_running:
            # 在新线程中启动监控
            threading.Thread(target=monitor.start_monitoring, daemon=True).start()
            return jsonify({
                'success': True,
                'message': 'V2系统监控启动中...'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'V2系统监控已在运行'
            })
    except Exception as e:
        logger.error(f"启动监控失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/stop_monitor', methods=['POST'])
def stop_monitor():
    """停止监控"""
    try:
        global monitor
        if monitor and monitor.is_running:
            monitor.stop_monitoring()
            return jsonify({
                'success': True,
                'message': 'V2系统监控已停止'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'V2系统监控未在运行'
            })
    except Exception as e:
        logger.error(f"停止监控失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/manual_scan', methods=['POST'])
def manual_scan():
    """手动扫描"""
    try:
        global monitor
        if not monitor:
            monitor = V2OptionMonitor()
        
        big_options = monitor.manual_scan()
        return jsonify({
            'success': True,
            'data': big_options,
            'count': len(big_options),
            'message': f'扫描完成，发现 {len(big_options)} 笔大单期权'
        })
    except Exception as e:
        logger.error(f"手动扫描失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='V2系统Web监控面板')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    logger.info(f"V2系统Web面板启动: http://{args.host}:{args.port}")
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )

if __name__ == '__main__':
    main()