# 港股期权大单监控系统

## 系统概述

本系统提供港股期权大单实时监控功能，支持V1和V2两个版本，具备完整的数据存储、分析和通知功能。

## 快速启动

### V1系统（原版本）
```bash
# 在项目根目录启动
python option_monitor.py
```

### V2系统（优化版本）
```bash
# 方式1: 使用启动脚本（推荐）
python start_v2_monitor.py --mode monitor

# 方式2: 进入v2_system目录启动
cd v2_system
python option_monitor_v2.py --mode monitor
```

## 系统特性

### 🎯 核心功能
- **实时监控**: 7×24小时港股期权大单监控
- **智能分析**: 期权Greeks计算、隐含波动率分析
- **多渠道通知**: 企微、Mac通知、控制台输出
- **数据存储**: SQLite时序数据库，支持历史数据查询
- **Web界面**: V2系统提供现代化管理界面

### 🔧 技术架构
- **后台线程**: 专门的API交互线程，处理股票订阅和回调
- **数据缓存**: 股票数据全量缓存，减少API调用
- **事件驱动**: 基于事件的架构设计，高效处理实时数据
- **容错机制**: 自动重连、错误恢复、数据备份

## 系统对比

| 特性 | V1系统 | V2系统 |
|------|--------|--------|
| 启动方式 | 根目录直接启动 | 支持根目录启动 |
| 数据存储 | 文件缓存 | SQLite数据库 |
| Web界面 | 基础界面 | 现代化界面 |
| 后台线程 | 集成在主程序 | 独立API管理器 |
| 配置管理 | config.py | 独立配置系统 |
| 通知系统 | 企微+Mac | 企微+Mac（独立） |

## 命令行参数

### V2系统参数
```bash
# 监控模式（默认）
python start_v2_monitor.py --mode monitor

# 扫描模式
python start_v2_monitor.py --mode scan

# 状态检查
python start_v2_monitor.py --mode status

# 测试模式
python start_v2_monitor.py --mode test

# 配置检查
python start_v2_monitor.py --config-check
```

## 配置说明

### V1系统配置
- 配置文件: `config.py`
- 缓存目录: `data/`
- 日志目录: `logs/`

### V2系统配置
- 配置文件: `v2_system/config.py`
- 数据库: `v2_system/data/options_v2.db`
- 缓存目录: `v2_system/data/`
- 日志目录: `v2_system/logs/`

## 期权代码格式

系统支持港股期权标准格式：
```
HK.{股票代码}{YYMMDD}{C/P}{执行价格}

示例:
- HK.TCH250919C670000  # 腾讯 2025-09-19 看涨 67.0000
- HK.BIU250919C120000  # 哔哩哔哩 2025-09-19 看涨 12.0000  
- HK.JDC250929P122500  # 京东 2025-09-29 看跌 12.2500
```

## 通知配置

### 企业微信通知
```python
# 在config.py中配置
WEWORK_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

### Mac通知
系统自动使用macOS原生通知，无需额外配置。

## 依赖安装

```bash
# 基础依赖
pip install futu-api pandas numpy requests flask

# V2系统额外依赖
pip install scipy  # 用于期权Greeks计算
```

## 故障排除

### 常见问题

1. **API连接失败**
   - 确保富途OpenD客户端正在运行
   - 检查端口11111是否被占用
   - 验证网络连接

2. **期权数据获取失败**
   - 确认在港股交易时间内运行
   - 检查股票代码是否正确
   - 清理缓存文件重新获取

3. **通知发送失败**
   - 检查企微webhook URL配置
   - 确认Mac通知权限设置

### 日志查看
```bash
# V1系统日志
tail -f logs/option_monitor.log

# V2系统日志
tail -f v2_system/logs/option_monitor_v2.log
```

## 开发说明

### 项目结构
```
large_stock_options_monitor/
├── option_monitor.py          # V1系统主程序
├── start_v2_monitor.py        # V2系统启动脚本
├── config.py                  # V1系统配置
├── utils/                     # V1系统工具模块
├── core/                      # V1系统核心模块
├── v2_system/                 # V2系统独立目录
│   ├── option_monitor_v2.py   # V2系统主程序
│   ├── config.py              # V2系统配置
│   ├── utils/                 # V2系统工具模块
│   └── core/                  # V2系统核心模块
├── data/                      # V1系统数据目录
├── logs/                      # V1系统日志目录
└── templates/                 # Web界面模板
```

### 期权解析器
系统使用统一的期权代码解析器：
- V1: `utils/option_code_parser.py`
- V2: `v2_system/utils/option_code_parser.py`

支持正则表达式精确匹配期权格式，提取股票代码、到期日、期权类型和执行价格。

## 更新日志

### V2.0 (2025-09-12)
- ✅ 创建完全独立的V2系统
- ✅ 实现后台API交互线程
- ✅ 添加SQLite时序数据库
- ✅ 统一期权代码解析逻辑
- ✅ 支持从根目录启动V2系统
- ✅ 修复所有期权类型判断错误
- ✅ 完善错误处理和自动重连

### V1.x (历史版本)
- 基础期权监控功能
- 企微和Mac通知
- 文件缓存系统
- Web管理界面

## 许可证

本项目仅供学习和研究使用。