# -*- coding: utf-8 -*-
"""
V2系统配置文件 - 独立于V1版本
"""

import os
from typing import Dict, Any, List

# ==================== 富途API配置 ====================
FUTU_CONFIG = {
    'host': '127.0.0.1',
    'port': 11111,
    'unlock_pwd': '',  # 请填入您的交易密码
    'market': 'HK',
    'security_firm': 'FUTUSECURITIES',
    'is_encrypt': False,
    'rsa_path': None,
    'auto_reconnect': True,
    'max_reconnect_attempts': 10,
    'reconnect_interval': 30,  # 秒
    'heartbeat_interval': 60,  # 秒
}

# ==================== 数据库配置 ====================
DATABASE_CONFIG = {
    'db_path': 'data/v2_options_monitor.db',
    'backup_enabled': True,
    'backup_interval': 24,  # 小时
    'backup_keep_days': 30,
    'auto_cleanup_enabled': True,
    'cleanup_days': 90,  # 保留90天数据
    'batch_size': 1000,
    'connection_timeout': 30,
}

# ==================== 监控股票配置 ====================
MONITOR_STOCKS = [
    'HK.00700',  # 腾讯控股
    'HK.09988',  # 阿里巴巴
    'HK.03690',  # 美团
    'HK.01810',  # 小米集团
    'HK.09618',  # 京东集团
    'HK.02318',  # 中国平安
    'HK.00388',  # 香港交易所
    'HK.00981',  # 中芯国际
    'HK.09888',  # 百度集团-SW
    'HK.01024',  # 快手-W
    'HK.02269',  # 药明生物
    'HK.00175',  # 吉利汽车
    'HK.01211',  # 比亚迪股份
    'HK.02015',  # 理想汽车-W
    'HK.09868',  # 小鹏汽车-W
]

# ==================== 期权过滤配置 ====================
OPTION_FILTERS = {
    'default': {
        'min_volume': 10,           # 最小成交量
        'min_turnover': 50000,      # 最小成交额(港币)
        'min_price': 0.001,         # 最小期权价格
        'max_price': 8,          # 最大期权价格
        'min_days_to_expiry': 1,    # 最小到期天数
        'max_days_to_expiry': 30,  # 最大到期天数
        'enable_call': True,        # 监控看涨期权
        'enable_put': True,         # 监控看跌期权
        'min_importance_score': 60, # 最小重要性分数
    },
    
    # 特定股票的过滤配置
    'HK.00700': {  # 腾讯控股
        'min_volume': 20,
        'min_turnover': 100000,
        'min_importance_score': 70,
    },
    
    'HK.09988': {  # 阿里巴巴
        'min_volume': 15,
        'min_turnover': 80000,
        'min_importance_score': 65,
    },
    
    'HK.03690': {  # 美团
        'min_volume': 15,
        'min_turnover': 80000,
        'min_importance_score': 65,
    },
}

# ==================== 通知配置 ====================
NOTIFICATION_V2 = {
    # 控制台通知
    'enable_console': True,
    
    # Mac系统通知
    'enable_mac_notification': True,
    
    # 邮件通知
    'enable_email': False,
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'username': '',  # 发送邮箱
        'password': '',  # 邮箱密码或应用密码
        'to_emails': [],  # 接收邮箱列表
    },
    
    # 企业微信机器人通知
    'enable_wework_bot': True,
    'wework_config': {
        'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=a478c69a-6b62-4b29-b22f-bdf649f53eed',  # 主要webhook URL
        'extra_webhook_urls': [],  # 额外的webhook URL列表
        'mentioned_list': [],  # @用户列表
        'mentioned_mobile_list': [],  # @手机号列表
        'enable_summary': True,  # 启用汇总通知
        'summary_interval': 300,  # 汇总间隔(秒)
    },
    
    # 通知频率控制
    'notification_interval': 60,  # 同一期权通知间隔(秒)
    'max_notifications_per_hour': 100,  # 每小时最大通知数
}

# ==================== 交易时间配置 ====================
TRADING_HOURS = {
    'market_open': '09:30',
    'market_close': '16:00',
    'lunch_break_start': '12:00',
    'lunch_break_end': '13:00',
    'timezone': 'Asia/Hong_Kong',
}

# ==================== 系统配置 ====================
SYSTEM_CONFIG = {
    # 日志配置
    'log_level': 'INFO',
    'log_file': 'logs/v2_option_monitor.log',
    'log_max_size': 50 * 1024 * 1024,  # 50MB
    'log_backup_count': 5,
    'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    
    # 性能配置
    'max_workers': 4,
    'cache_size': 10000,
    'cache_ttl': 300,  # 缓存TTL(秒)
    'gc_interval': 3600,  # 垃圾回收间隔(秒)
    
    # 监控配置
    'monitor_interval': 5,  # 监控间隔(秒)
    'data_fetch_interval': 3,  # 数据获取间隔(秒)
    'health_check_interval': 60,  # 健康检查间隔(秒)
    
    # Web界面配置
    'web_host': '0.0.0.0',
    'web_port': 8289,  # V2使用不同端口
    'web_debug': False,
    'web_auto_reload': False,
}

# ==================== 分析配置 ====================
ANALYSIS_CONFIG = {
    # Greeks计算配置
    'enable_greeks': True,
    'risk_free_rate': 0.03,  # 无风险利率
    'dividend_yield': 0.02,  # 股息率
    
    # 波动率配置
    'volatility_window': 30,  # 历史波动率计算窗口(天)
    'min_volatility': 0.1,   # 最小波动率
    'max_volatility': 2.0,   # 最大波动率
    
    # 风险评估配置
    'risk_thresholds': {
        'low': 30,     # 低风险阈值
        'medium': 60,  # 中风险阈值
        'high': 80,    # 高风险阈值
    },
    
    # 重要性评分配置
    'importance_weights': {
        'volume_weight': 0.3,      # 成交量权重
        'turnover_weight': 0.3,    # 成交额权重
        'moneyness_weight': 0.2,   # 价值状态权重
        'time_weight': 0.1,        # 时间价值权重
        'volatility_weight': 0.1,  # 波动率权重
    },
}

# ==================== 辅助函数 ====================
def get_option_filter(stock_code: str) -> Dict[str, Any]:
    """获取股票的期权过滤配置"""
    default_filter = OPTION_FILTERS['default'].copy()
    stock_filter = OPTION_FILTERS.get(stock_code, {})
    default_filter.update(stock_filter)
    return default_filter

def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    stock_names = {
        'HK.00700': '腾讯控股',
        'HK.09988': '阿里巴巴',
        'HK.03690': '美团',
        'HK.01810': '小米集团',
        'HK.09618': '京东集团',
        'HK.02318': '中国平安',
        'HK.00388': '香港交易所',
        'HK.00981': '中芯国际',
        'HK.02020': '安踏体育',
        'HK.01024': '快手',
    }
    return stock_names.get(stock_code, stock_code)

def validate_config():
    """验证配置有效性"""
    errors = []
    
    # 验证富途配置
    if not FUTU_CONFIG.get('host'):
        errors.append("富途API主机地址未配置")
    
    if not isinstance(FUTU_CONFIG.get('port'), int) or FUTU_CONFIG['port'] <= 0:
        errors.append("富途API端口配置无效")
    
    # 验证监控股票
    if not MONITOR_STOCKS:
        errors.append("未配置监控股票")
    
    # 验证通知配置
    if NOTIFICATION_V2.get('enable_wework_bot'):
        wework_config = NOTIFICATION_V2.get('wework_config', {})
        if not wework_config.get('webhook_url'):
            errors.append("企业微信webhook URL未配置")
    
    if NOTIFICATION_V2.get('enable_email'):
        email_config = NOTIFICATION_V2.get('email_config', {})
        if not email_config.get('username') or not email_config.get('password'):
            errors.append("邮件配置不完整")
    
    # 验证数据库配置
    db_path = DATABASE_CONFIG.get('db_path')
    if db_path:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建数据库目录: {e}")
    
    return errors

# ==================== 环境变量支持 ====================
def load_from_env():
    """从环境变量加载配置"""
    # 富途配置
    if os.getenv('FUTU_HOST'):
        FUTU_CONFIG['host'] = os.getenv('FUTU_HOST')
    
    if os.getenv('FUTU_PORT'):
        try:
            FUTU_CONFIG['port'] = int(os.getenv('FUTU_PORT'))
        except ValueError:
            pass
    
    if os.getenv('FUTU_UNLOCK_PWD'):
        FUTU_CONFIG['unlock_pwd'] = os.getenv('FUTU_UNLOCK_PWD')
    
    # 企业微信配置
    if os.getenv('WEWORK_WEBHOOK_URL'):
        NOTIFICATION_V2['wework_config']['webhook_url'] = os.getenv('WEWORK_WEBHOOK_URL')
    
    # 邮件配置
    if os.getenv('EMAIL_USERNAME'):
        NOTIFICATION_V2['email_config']['username'] = os.getenv('EMAIL_USERNAME')
    
    if os.getenv('EMAIL_PASSWORD'):
        NOTIFICATION_V2['email_config']['password'] = os.getenv('EMAIL_PASSWORD')

# 自动加载环境变量
load_from_env()

# 导出主要配置对象（保持与V1兼容的接口）
NOTIFICATION = NOTIFICATION_V2
MONITOR_STOCK_CODES = MONITOR_STOCKS

if __name__ == '__main__':
    # 配置验证
    errors = validate_config()
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("配置验证通过")
        
    # 显示配置摘要
    print(f"\nV2配置摘要:")
    print(f"  监控股票: {len(MONITOR_STOCKS)} 只")
    print(f"  富途API: {FUTU_CONFIG['host']}:{FUTU_CONFIG['port']}")
    print(f"  数据库: {DATABASE_CONFIG['db_path']}")
    print(f"  Web端口: {SYSTEM_CONFIG['web_port']}")
    print(f"  通知方式: 控制台={NOTIFICATION_V2['enable_console']}, Mac={NOTIFICATION_V2['enable_mac_notification']}, 企微={NOTIFICATION_V2['enable_wework_bot']}, 邮件={NOTIFICATION_V2['enable_email']}")