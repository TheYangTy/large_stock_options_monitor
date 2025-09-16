#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2系统多市场数据库浏览器 - Flask Web应用
用于查看和查询港股和美股期权交易数据
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

from config import get_database_config
from utils.database_manager import get_database_manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'v2_option_monitor_secret_key'

# 初始化数据库管理器
hk_db_manager = get_database_manager('HK')
us_db_manager = get_database_manager('US')

def get_db_manager(market='HK'):
    """根据市场获取数据库管理器"""
    return us_db_manager if market == 'US' else hk_db_manager

@app.route('/')
def index():
    """主页 - 显示数据概览"""
    try:
        # 获取港股和美股统计
        hk_stats = get_database_stats('HK')
        us_stats = get_database_stats('US')
        
        return render_template('index.html', 
                             hk_stats=hk_stats, 
                             us_stats=us_stats)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/stats')
def api_stats():
    """API - 获取数据库统计信息"""
    try:
        market = request.args.get('market', 'HK')
        stats = get_database_stats(market)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/trades')
@app.route('/trades/<market>')
def trades(market='HK'):
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
        trades_data = get_trades_data(market, page, per_page, stock_code, option_code, date_from, date_to)
        
        return render_template('trades.html', 
                             trades=trades_data['trades'],
                             pagination=trades_data['pagination'],
                             market=market,
                             market_name='港股' if market == 'HK' else '美股',
                             currency='港币' if market == 'HK' else '美元',
                             filters={
                                 'stock_code': stock_code,
                                 'option_code': option_code,
                                 'date_from': date_from,
                                 'date_to': date_to
                             })
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/trades')
@app.route('/api/trades/<market>')
def api_trades(market='HK'):
    """API - 获取交易记录"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        stock_code = request.args.get('stock_code', '')
        option_code = request.args.get('option_code', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        trades_data = get_trades_data(market, page, per_page, stock_code, option_code, date_from, date_to)
        return jsonify(trades_data)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/stocks')
@app.route('/stocks/<market>')
def stocks(market='HK'):
    """股票统计页面"""
    try:
        stock_stats = get_stock_stats(market)
        return render_template('stocks.html', 
                             stocks=stock_stats,
                             market=market,
                             market_name='港股' if market == 'HK' else '美股',
                             currency='港币' if market == 'HK' else '美元')
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/api/stocks')
@app.route('/api/stocks/<market>')
def api_stocks(market='HK'):
    """API - 获取股票统计"""
    try:
        stock_stats = get_stock_stats(market)
        return jsonify(stock_stats)
    except Exception as e:
        return jsonify({'error': str(e)})

# 美股专用路由
@app.route('/us_stocks')
def us_stocks():
    """美股统计页面"""
    return stocks('US')

@app.route('/us_trades')
def us_trades():
    """美股交易记录页面"""
    return trades('US')

def get_database_stats(market='HK'):
    """获取数据库统计信息"""
    try:
        db_manager = get_db_manager(market)
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
                'market': market,
                'market_name': '港股' if market == 'HK' else '美股',
                'currency': '港币' if market == 'HK' else '美元',
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
        print(f"获取{market}市场统计信息失败: {e}")
        return {
            'market': market,
            'market_name': '港股' if market == 'HK' else '美股',
            'currency': '港币' if market == 'HK' else '美元',
            'total_trades': 0,
            'today_trades': 0,
            'stock_count': 0,
            'option_count': 0,
            'total_turnover': 0,
            'earliest_record': None,
            'latest_record': None,
            'database_path': ''
        }

def get_trades_data(market='HK', page=1, per_page=50, stock_code='', option_code='', date_from='', date_to=''):
    """获取交易记录数据"""
    try:
        db_manager = get_db_manager(market)
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
                       COALESCE(si.stock_name, ot.stock_name, '') as stock_name,
                       ot.option_open_interest,
                       ot.option_net_open_interest,
                       ot.open_interest_diff as option_open_interest_diff,
                       ot.net_open_interest_diff as option_net_open_interest_diff
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
        print(f"获取{market}市场交易数据失败: {e}")
        return {'trades': [], 'pagination': {}}

def get_stock_stats(market='HK'):
    """获取股票统计信息，按Put和Call分别统计
    统计今天的数据，每个期权只取最新的一个数据
    净持仓变化汇总 = 今天股票净持仓汇总 - 昨天股票净持仓汇总
    """
    try:
        db_manager = get_db_manager(market)
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取今天和昨天的日期
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 查询今天和昨天的数据，计算股票粒度的净持仓变化
            cursor.execute("""
                WITH today_latest AS (
                    SELECT 
                        ot.stock_code,
                        ot.option_code,
                        ot.option_type,
                        ot.volume,
                        ot.turnover,
                        ot.price,
                        ot.timestamp,
                        ot.option_open_interest,
                        ot.option_net_open_interest,
                        ROW_NUMBER() OVER (
                            PARTITION BY ot.option_code 
                            ORDER BY ot.timestamp DESC
                        ) as rn
                    FROM option_trades ot
                    WHERE DATE(ot.timestamp) = ?
                ),
                yesterday_latest AS (
                    SELECT 
                        ot.stock_code,
                        ot.option_code,
                        ot.option_type,
                        ot.option_open_interest,
                        ot.option_net_open_interest,
                        ROW_NUMBER() OVER (
                            PARTITION BY ot.option_code 
                            ORDER BY ot.timestamp DESC
                        ) as rn
                    FROM option_trades ot
                    WHERE DATE(ot.timestamp) = ?
                ),
                today_summary AS (
                    SELECT 
                        tl.stock_code,
                        tl.option_type,
                        COUNT(*) as trade_count,
                        SUM(tl.volume) as total_volume,
                        SUM(tl.turnover) as total_turnover,
                        AVG(tl.price) as avg_price,
                        MAX(tl.timestamp) as latest_trade,
                        SUM(COALESCE(tl.option_open_interest, 0)) as total_open_interest,
                        SUM(COALESCE(tl.option_net_open_interest, 0)) as today_total_net_open_interest
                    FROM today_latest tl
                    WHERE tl.rn = 1
                    GROUP BY tl.stock_code, tl.option_type
                ),
                yesterday_summary AS (
                    SELECT 
                        yl.stock_code,
                        yl.option_type,
                        SUM(COALESCE(yl.option_net_open_interest, 0)) as yesterday_total_net_open_interest
                    FROM yesterday_latest yl
                    WHERE yl.rn = 1
                    GROUP BY yl.stock_code, yl.option_type
                )
                SELECT 
                    ts.stock_code,
                    COALESCE(si.stock_name, '') as stock_name,
                    COALESCE(ts.option_type, 'Unknown') as option_type,
                    ts.trade_count,
                    ts.total_volume,
                    ts.total_turnover,
                    ts.avg_price,
                    ts.latest_trade,
                    ts.total_open_interest,
                    ts.today_total_net_open_interest,
                    COALESCE(ys.yesterday_total_net_open_interest, 0) as yesterday_total_net_open_interest,
                    (ts.today_total_net_open_interest - COALESCE(ys.yesterday_total_net_open_interest, 0)) as net_open_interest_change
                FROM today_summary ts
                LEFT JOIN yesterday_summary ys ON ts.stock_code = ys.stock_code AND ts.option_type = ys.option_type
                LEFT JOIN stock_info si ON ts.stock_code = si.stock_code
                ORDER BY ts.total_turnover DESC
            """, (today, yesterday))
            
            stocks = []
            for row in cursor.fetchall():
                stock = {
                    'stock_code': row[0],
                    'stock_name': row[1],
                    'option_type': row[2],
                    'trade_count': row[3],
                    'total_volume': row[4] or 0,
                    'total_turnover': row[5] or 0,
                    'avg_price': round(row[6], 3) if row[6] else 0,
                    'latest_trade': row[7],
                    'total_open_interest': row[8] or 0,
                    'total_net_open_interest': row[9] or 0,
                    'yesterday_total_net_open_interest': row[10] or 0,
                    'total_net_open_interest_diff': row[11] or 0  # 这是正确的股票粒度净持仓变化
                }
                if stock['latest_trade']:
                    stock['formatted_latest'] = datetime.fromisoformat(stock['latest_trade']).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    stock['formatted_latest'] = ''
                stocks.append(stock)
            
            return stocks
    except Exception as e:
        print(f"获取{market}市场股票统计失败: {e}")
        return []

if __name__ == '__main__':
    # 确保模板目录存在
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print("V2多市场期权监控数据库浏览器启动中...")
    print(f"港股数据库: {hk_db_manager.db_path}")
    print(f"美股数据库: {us_db_manager.db_path}")
    print("访问地址: http://localhost:5001")
    
    app.run(debug=True, host='0.0.0.0', port=5001)