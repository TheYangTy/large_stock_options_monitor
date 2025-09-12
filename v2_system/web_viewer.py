#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2系统数据库浏览器 - Flask Web应用
用于查看和查询数据库中的期权交易数据
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import json

# 添加V2系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_CONFIG
from utils.database_manager import V2DatabaseManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'v2_option_monitor_secret_key'

# 初始化数据库管理器
db_manager = V2DatabaseManager()

@app.route('/')
def index():
    """主页 - 显示数据概览"""
    try:
        # 获取数据统计
        stats = get_database_stats()
        return render_template('index.html', stats=stats)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/stats')
def api_stats():
    """API - 获取数据库统计信息"""
    try:
        stats = get_database_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/trades')
def trades():
    """交易记录页面"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        stock_code = request.args.get('stock_code', '')
        option_code = request.args.get('option_code', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # 查询数据
        trades_data = get_trades_data(page, per_page, stock_code, option_code, date_from, date_to)
        
        return render_template('trades.html', 
                             trades=trades_data['trades'],
                             pagination=trades_data['pagination'],
                             filters={
                                 'stock_code': stock_code,
                                 'option_code': option_code,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/trades')
def api_trades():
    """API - 获取交易记录"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        stock_code = request.args.get('stock_code', '')
        option_code = request.args.get('option_code', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        trades_data = get_trades_data(page, per_page, stock_code, option_code, date_from, date_to)
        return jsonify(trades_data)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/stocks')
def stocks():
    """股票统计页面"""
    try:
        stock_stats = get_stock_stats()
        return render_template('stocks.html', stocks=stock_stats)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/stocks')
def api_stocks():
    """API - 获取股票统计"""
    try:
        stock_stats = get_stock_stats()
        return jsonify(stock_stats)
    except Exception as e:
        return jsonify({'error': str(e)})

def get_database_stats():
    """获取数据库统计信息"""
    try:
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM option_trades")
            total_trades = cursor.fetchone()[0]
            
            # 今日记录数
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM option_trades WHERE DATE(timestamp) = ?", (today,))
            today_trades = cursor.fetchone()[0]
            
            # 最早和最新记录时间
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM option_trades")
            min_time, max_time = cursor.fetchone()
            
            # 股票数量
            cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM option_trades")
            stock_count = cursor.fetchone()[0]
            
            # 期权代码数量
            cursor.execute("SELECT COUNT(DISTINCT option_code) FROM option_trades")
            option_count = cursor.fetchone()[0]
            
            # 总成交金额
            cursor.execute("SELECT SUM(turnover) FROM option_trades")
            total_turnover = cursor.fetchone()[0] or 0
            
            return {
                'total_trades': total_trades,
                'today_trades': today_trades,
                'stock_count': stock_count,
                'option_count': option_count,
                'total_turnover': total_turnover,
                'earliest_record': min_time,
                'latest_record': max_time,
                'database_path': db_manager.db_path
            }
    except Exception as e:
        print(f"获取统计信息失败: {e}")
        return {}

def get_trades_data(page=1, per_page=50, stock_code='', option_code='', date_from='', date_to=''):
    """获取交易记录数据"""
    try:
        with sqlite3.connect(db_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if stock_code:
                where_conditions.append("ot.stock_code LIKE ?")
                params.append(f"%{stock_code}%")
            
            if option_code:
                where_conditions.append("ot.option_code LIKE ?")
                params.append(f"%{option_code}%")
            
            if date_from:
                where_conditions.append("DATE(ot.timestamp) >= ?")
                params.append(date_from)
            
            if date_to:
                where_conditions.append("DATE(ot.timestamp) <= ?")
                params.append(date_to)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # 获取总数
            count_query = f"""
                SELECT COUNT(*) FROM option_trades ot
                LEFT JOIN stock_info si ON ot.stock_code = si.stock_code
                {where_clause}
            """
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # 计算分页
            offset = (page - 1) * per_page
            total_pages = (total_count + per_page - 1) // per_page
            
            # 获取数据
            data_query = f"""
                SELECT ot.*, 
                       COALESCE(si.stock_name, ot.stock_name, '') as stock_name
                FROM option_trades ot
                LEFT JOIN stock_info si ON ot.stock_code = si.stock_code
                {where_clause}
                ORDER BY ot.timestamp DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [per_page, offset])
            
            trades = []
            for row in cursor.fetchall():
                trade = dict(row)
                # 格式化时间
                if trade['timestamp']:
                    trade['formatted_time'] = datetime.fromisoformat(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                trades.append(trade)
            
            return {
                'trades': trades,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages,
                    'prev_num': page - 1 if page > 1 else None,
                    'next_num': page + 1 if page < total_pages else None
                }
            }
    except Exception as e:
        print(f"获取交易数据失败: {e}")
        return {'trades': [], 'pagination': {}}

def get_stock_stats():
    """获取股票统计信息"""
    try:
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    ot.stock_code,
                    COALESCE(si.stock_name, ot.stock_name, '') as stock_name,
                    COUNT(*) as trade_count,
                    SUM(ot.volume) as total_volume,
                    SUM(ot.turnover) as total_turnover,
                    AVG(ot.price) as avg_price,
                    MAX(ot.timestamp) as latest_trade
                FROM option_trades ot
                LEFT JOIN stock_info si ON ot.stock_code = si.stock_code
                GROUP BY ot.stock_code
                ORDER BY total_turnover DESC
            """)
            
            stocks = []
            for row in cursor.fetchall():
                stock = {
                    'stock_code': row[0],
                    'stock_name': row[1],
                    'trade_count': row[2],
                    'total_volume': row[3],
                    'total_turnover': row[4],
                    'avg_price': round(row[5], 3) if row[5] else 0,
                    'latest_trade': row[6]
                }
                if stock['latest_trade']:
                    stock['formatted_latest'] = datetime.fromisoformat(stock['latest_trade']).strftime('%Y-%m-%d %H:%M:%S')
                stocks.append(stock)
            
            return stocks
    except Exception as e:
        print(f"获取股票统计失败: {e}")
        return []

if __name__ == '__main__':
    # 确保模板目录存在
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print("V2期权监控数据库浏览器启动中...")
    print(f"数据库路径: {db_manager.db_path}")
    print("访问地址: http://localhost:5001")
    
    app.run(debug=True, host='0.0.0.0', port=5001)