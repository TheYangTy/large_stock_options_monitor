# V2系统 - 港股期权大单监控

## 系统特点

V2系统是完全独立的港股期权大单监控系统，与V1系统完全隔离：

- ✅ **完全独立**: 所有文件、配置、缓存都与V1系统分离
- ✅ **大单监控**: 集成V1的大单监控功能，支持实时监控
- ✅ **多种通知**: 支持企微推送和Mac系统通知
- ✅ **Web界面**: 现代化的Web监控面板
- ✅ **数据存储**: 独立的数据库存储所有期权数据
- ✅ **后台运行**: 支持后台守护进程模式

## 目录结构

```
v2_system/
├── config.py                 # V2系统配置文件
├── option_monitor_v2.py       # 主监控程序
├── web_dashboard_v2.py        # Web监控面板
├── start_v2.py               # 启动脚本
├── core/                     # 核心模块
│   ├── __init__.py
│   ├── api_manager.py        # API管理器
│   ├── database_manager.py   # 数据库管理器
│   └── option_analyzer.py    # 期权分析器
├── utils/                    # 工具模块
│   ├── __init__.py
│   ├── big_options_processor.py  # 大单处理器
│   ├── notifier.py           # 通知模块
│   ├── logger.py             # 日志模块
│   ├── mac_notifier.py       # Mac通知
│   └── data_handler.py       # 数据处理器
├── templates/                # Web模板
│   └── dashboard_v2.html     # 监控面板模板
├── data/                     # 数据目录
├── logs/                     # 日志目录
└── screenshots/              # 截图目录
```

## 快速开始

### 1. 安装依赖

```bash
cd v2_system
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config.py` 文件，配置：
- 富途OpenD连接信息
- 企微Webhook地址
- 监控股票列表
- 过滤条件

### 3. 启动方式

#### 方式一：直接启动监控
```bash
python start_v2.py --mode monitor
```

#### 方式二：启动Web界面
```bash
python start_v2.py --mode web
```
然后访问: http://127.0.0.1:5001

#### 方式三：后台运行
```bash
python start_v2.py --mode monitor --daemon
```

### 4. 其他命令

```bash
# 单次扫描
python start_v2.py --mode scan

# 查看状态
python start_v2.py --mode status

# 系统测试
python start_v2.py --mode test
```

## 功能特性

### 大单监控
- 实时监控港股期权大单交易
- 智能过滤和重要性评分
- 支持多种通知方式

### 数据存储
- SQLite数据库存储所有期权数据
- 支持历史数据查询和分析
- 自动数据清理和备份

### Web监控面板
- 现代化响应式界面
- 实时状态监控
- 历史数据查看
- 手动操作控制

### 通知系统
- 企微群机器人推送
- Mac系统原生通知
- 智能通知频率控制
- 大单汇总通知

## 配置说明

### 富途OpenD配置
```python
FUTU_CONFIG = {
    'host': '127.0.0.1',
    'port': 11111,
    'market': 'HK'
}
```

### 监控股票配置
```python
MONITOR_STOCKS = [
    'HK.00700',  # 腾讯控股
    'HK.09988',  # 阿里巴巴
    # ... 更多股票
]
```

### 过滤条件配置
```python
OPTION_FILTERS = {
    'min_turnover': 1000000,      # 最小成交额100万
    'min_volume': 100,            # 最小成交量
    'max_days_to_expiry': 90,     # 最大到期天数
    'min_moneyness': 0.8,         # 最小价值度
    'max_moneyness': 1.2          # 最大价值度
}
```

## 与V1系统的区别

| 特性 | V1系统 | V2系统 |
|------|--------|--------|
| 文件独立性 | 共享部分文件 | 完全独立 |
| 缓存文件 | 共享缓存 | 独立缓存 |
| 配置文件 | config.py | config.py (独立) |
| 数据存储 | 简单文件 | SQLite数据库 |
| Web界面 | 基础界面 | 现代化界面 |
| 通知系统 | 基础通知 | 增强通知 |
| 后台运行 | 不支持 | 支持守护进程 |

## 日志和调试

### 日志文件位置
- 主程序日志: `logs/v2_option_monitor.log`
- Web界面日志: `logs/v2_web_dashboard.log`
- 错误日志: `logs/v2_error.log`

### 调试模式
```bash
# 启用调试模式
python option_monitor_v2.py --mode test

# Web调试模式
python web_dashboard_v2.py --debug
```

## 常见问题

### 1. 富途连接失败
- 检查OpenD是否启动
- 确认端口号是否正确
- 检查防火墙设置

### 2. 通知发送失败
- 检查企微Webhook地址
- 确认网络连接正常
- 查看日志文件详细错误

### 3. 数据库错误
- 检查data目录权限
- 确认磁盘空间充足
- 重新初始化数据库

## 技术支持

如有问题，请查看：
1. 日志文件中的错误信息
2. 系统状态和配置
3. 富途OpenD连接状态

## 更新日志

### v2.0.0 (2024-01-XX)
- 完全独立的V2系统
- 集成大单监控功能
- 现代化Web界面
- 增强的通知系统
- SQLite数据库存储